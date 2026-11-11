#!/usr/bin/env python3
"""Generate Azra's features and run a separate controlled Ridge ablation offline."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import sklearn

from callup.contract import load
from callup.modeling import fit_ridge, labeled_partitions, select_features
from callup.ridge_ablation import (
    BATTED_PREDICTORS,
    CONFIGURATIONS,
    coverage_tables,
    experiment,
    join_features,
)
from scripts import build_batted_features as azra

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/processed/ridge_batted_ablation_v1"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight(study):
    """Reject duplicates before Azra's loader could keep the first; check seasonal AAA scope."""
    teams = pd.read_csv(azra.TEAMS_CSV)
    study_keys = set(map(tuple, study[["player_id", "season"]].to_numpy()))
    summary = []
    keys = []
    anomalies = []
    for path in azra.PITCH_FILES:
        frame = pd.read_csv(path, usecols=[*azra.PITCH_COLUMNS, "game_date", "events"])
        if frame[azra.PITCH_KEY].isna().any().any():
            raise ValueError("Missing pitch key")
        for column, lower, upper in [('launch_speed', 0, 130), ('launch_angle', -90, 90)]:
            if not pd.to_numeric(frame[column], errors='raise').dropna().between(lower, upper).all():
                raise ValueError(f'Invalid raw batted measurement: {column}')
        in_play = frame.loc[frame.description.eq('hit_into_play') & frame.in_cohort]
        repeated = in_play.loc[in_play.duplicated(['game_pk', 'at_bat_number'], keep=False)].copy()
        anomalies.append(repeated)
        keys.append(frame[azra.PITCH_KEY])
        dates = pd.to_datetime(frame.game_date)
        if not dates.dt.year.eq(frame.season).all():
            raise ValueError("Pitch date does not belong to feature season")
        if frame.in_cohort.dtype != bool:
            raise ValueError("Nonboolean cohort flag")
        expected_flag = pd.Series([(int(p), int(y)) in study_keys for p, y in zip(frame.batter, frame.season, strict=True)], index=frame.index)
        if not frame.in_cohort.eq(expected_flag).all():
            raise ValueError("Archive cohort flag does not match study keys")
        for year, group in frame.groupby("season"):
            codes = set(teams.loc[teams.season.eq(year), "pitch_codes"].dropna())
            if not (group.home_team.isin(codes) & group.away_team.isin(codes)).all():
                raise ValueError("Pitch not in season-specific AAA team map")
        if frame.season.nunique() != 1 or int(frame.season.iloc[0]) not in (2023, 2024):
            raise ValueError("Unexpected feature season")
        summary.append({"path": str(path.relative_to(ROOT)), "rows": len(frame),
                        "cohort_pitches": int(frame.in_cohort.sum()), "sha256": sha256(path),
                        "repeated_in_play_pa": len(repeated[["game_pk", "at_bat_number"]].drop_duplicates()),
                        "nonterminal_in_play_rows": int(in_play.events.isna().sum()),
                        "first_date": str(dates.min().date()), "last_date": str(dates.max().date())})
    if pd.concat(keys, ignore_index=True).duplicated(azra.PITCH_KEY).any():
        raise ValueError("Duplicate pitch keys; refusing upstream first-copy deduplication")
    return summary, pd.concat(anomalies, ignore_index=True)


def build_features(study):
    source_summary, anomalies = preflight(study)
    pitches = azra.load_pitches(azra.load_aaa_teams())
    batted = azra.filter_batted_balls(pitches)
    features = azra.join_to_study(study[["player_id", "season"]], azra.summarize_batted_balls(batted), pitches)
    # Diagnose repeated in-play rows without changing Azra's feature definition.
    unmeasured_nonterminal = anomalies.loc[anomalies.events.isna()]
    if unmeasured_nonterminal[['launch_speed', 'launch_angle']].notna().any().any():
        raise ValueError('Repeated nonterminal batted row has measurements; scientific review required')
    marked = batted.merge(unmeasured_nonterminal[azra.PITCH_KEY].assign(flagged=True),
                          on=azra.PITCH_KEY, how='left', validate='one_to_one')
    diagnostic = azra.summarize_batted_balls(marked.loc[marked.flagged.isna()])
    original = features.sort_values(['player_id', 'season'])
    diagnostic = diagnostic.sort_values(['player_id', 'season'])
    np.testing.assert_allclose(original[BATTED_PREDICTORS].to_numpy(dtype=float),
                               diagnostic[BATTED_PREDICTORS].to_numpy(dtype=float), equal_nan=True, atol=1e-12, rtol=0)
    checks = []
    # Fixed key-based sample, never selected using outcomes or model scores.
    for year, group in study.groupby('season'):
        for pid in sorted(group.player_id)[:2]:
            balls = batted.loc[batted.batter.eq(pid) & batted.season.eq(year)]
            row = features.loc[features.player_id.eq(pid) & features.season.eq(year)].iloc[0]
            expected = {"n_bbe": len(balls), "n_ev": int(balls.launch_speed.notna().sum()),
                        "n_la": int(balls.launch_angle.notna().sum()),
                        "n_hard_hit": int(balls.launch_speed.ge(95).sum()),
                        "ev_mean": balls.launch_speed.mean(), "ev_p90": balls.launch_speed.quantile(.9),
                        "ev_max": balls.launch_speed.max(), "la_mean": balls.launch_angle.mean(),
                        "la_median": balls.launch_angle.median(), "la_std": balls.launch_angle.std(ddof=1)}
            for key, value in expected.items():
                if not np.isclose(float(row[key]), value, equal_nan=True, atol=1e-12):
                    raise ValueError("Batted aggregation spot-check failed")
            checks.append({"player_id": int(pid), "season": int(year), **expected})
    return features, source_summary, pd.DataFrame(checks), anomalies


def verify_benchmark(frame, metrics, predictions):
    """Reproduce the existing six-count fitting algorithm without writing its outputs."""
    train, test = labeled_partitions(frame)
    original = fit_ridge(train)
    model = metrics['models']['six_counts']
    if model['selected_alpha'] != float(original.best_params_['ridge__alpha']):
        raise ValueError("Six-count alpha differs from original benchmark")
    actual = predictions.loc[predictions.evaluation.eq('exploratory_holdout') & predictions.model.eq('six_counts')]
    expected = original.predict(select_features(test))
    np.testing.assert_allclose(actual.y_pred, expected, atol=1e-12, rtol=0)
    np.testing.assert_allclose(actual.y_true, test.mlb_woba, atol=0, rtol=0)
    np.testing.assert_allclose(model['selection_cv_mae'], -original.best_score_, atol=1e-12, rtol=0)
    evidence = {"existing_algorithm_reproduced": True, "prediction_tolerance": 1e-12}
    saved_metrics = ROOT / 'data/processed/model_metrics.json'
    saved_predictions = ROOT / 'data/processed/predictions.csv'
    if saved_metrics.exists() and saved_predictions.exists():
        prior = json.loads(saved_metrics.read_text())['models']['ridge']
        prior_predictions = pd.read_csv(saved_predictions).loc[lambda f:f.model.eq('ridge')]
        pd.testing.assert_frame_equal(actual[['player_id', 'season']].reset_index(drop=True),
                                      prior_predictions[['player_id', 'season']].reset_index(drop=True))
        np.testing.assert_allclose(actual.y_pred, prior_predictions.y_pred, atol=1e-12, rtol=0)
        np.testing.assert_allclose(actual.y_true, prior_predictions.y_true, atol=1e-12, rtol=0)
        assert model['selected_alpha'] == prior['selected_alpha']
        for metric in ['mae', 'rmse']:
            assert np.isclose(model['exploratory_holdout'][metric], prior[metric], atol=1e-12, rtol=0)
        evidence.update(saved_results_reproduced=True, saved_metrics_sha256=sha256(saved_metrics),
                        saved_predictions_sha256=sha256(saved_predictions))
    return evidence


def plot_results(predictions, deltas, output):
    os.environ.setdefault('MPLCONFIGDIR', str(output / 'matplotlib_cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for metric, marker in [('mae', 'o'), ('rmse', 's')]:
        axes[0].plot(deltas.fold + 1, deltas[f'delta_{metric}_plus_minus_six'], marker=marker, label=metric.upper())
    axes[0].axhline(0, color='gray', linestyle='--')
    axes[0].set(xlabel='Outer training-validation fold', ylabel='Added batted-ball error minus six-count error',
                title='Negative difference favors batted-ball features')
    axes[0].legend()
    oof = predictions.loc[predictions.evaluation.eq('nested_training_oof')]
    for name in CONFIGURATIONS:
        selected = oof.loc[oof.model.eq(name)]
        axes[1].scatter(selected.y_true, selected.y_pred, alpha=.6, label=name)
    limits = [min(oof.y_true.min(), oof.y_pred.min()) - .005, max(oof.y_true.max(), oof.y_pred.max()) + .005]
    axes[1].plot(limits, limits, color='gray', linestyle='--')
    axes[1].set(xlabel='Original provisional wOBA', ylabel='Nested out-of-fold prediction', title='Training only; 62 labeled players')
    axes[1].legend()
    fig.suptitle('PRELIMINARY Ridge ablation — frozen provisional outcome')
    fig.tight_layout()
    for extension in ['png', 'svg']:
        fig.savefig(output / f'training_comparison.{extension}', dpi=160)
    plt.close(fig)


def main():
    if ROOT / 'data/processed' not in OUTPUT.parents:
        raise ValueError('Outputs must remain under ignored data/processed/')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # Preserve the complete tracked snapshot plus pre-existing generated outputs outside this experiment.
    protected = {ROOT / p for p in subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines() if (ROOT / p).is_file()}
    protected.update(p for p in (ROOT / 'data/processed').rglob('*') if p.is_file() and OUTPUT not in p.parents)
    before = {str(p.relative_to(ROOT)): sha256(p) for p in sorted(protected)}
    study_path = ROOT / 'data/shared/processed/hitter_seasons.csv'
    study = load(study_path)
    if len(study) != 926:
        raise ValueError('Expected frozen 926-row study')
    features, source_summary, checks, anomalies = build_features(study)
    frame = join_features(study, features)
    missing, coverage = coverage_tables(frame)
    metrics, predictions, folds, deltas, assignments, grid = experiment(frame)
    metrics['benchmark_reproduction'] = verify_benchmark(frame, metrics, predictions)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip())
    provenance = {"study_sha256": sha256(study_path), "teams_sha256": sha256(azra.TEAMS_CSV),
                  "source_pitches": source_summary, "git_revision": revision, "git_dirty": dirty,
                  "code_sha256": {p: sha256(ROOT / p) for p in ['callup/ridge_ablation.py', 'scripts/ridge_batted_ablation.py', 'scripts/build_batted_features.py', 'callup/modeling.py']},
                  "versions": {"numpy": np.__version__, "pandas": pd.__version__, "sklearn": sklearn.__version__},
                  "audit_commit": "edb6fdf670d0e3f1a88f186a3160417199528419"}
    metrics['provenance'] = provenance
    predictions['data_version'] = 'sha256:' + provenance['study_sha256']
    predictions['code_version'] = revision
    predictions['code_dirty'] = dirty
    for name, table in [('features_batted', features), ('study_with_batted', frame), ('feature_missingness', missing),
                        ('measurement_coverage', coverage), ('feature_spot_checks', checks), ('batted_source_anomalies', anomalies), ('predictions', predictions),
                        ('outer_fold_metrics', folds), ('paired_fold_differences', deltas), ('fold_assignments', assignments), ('alpha_grid_scores', grid)]:
        table.to_csv(OUTPUT / f'{name}.csv', index=False)
    plot_results(predictions, deltas, OUTPUT)
    changed = [p for p, expected in before.items() if not (ROOT / p).is_file() or sha256(ROOT / p) != expected]
    if changed:
        raise ValueError(f'Protected input/artifact changed: {changed}')
    metrics['preservation'] = {"verified_files": len(before), "changed": []}
    (OUTPUT / 'preserved_inputs.json').write_text(json.dumps(before, indent=2) + '\n')
    (OUTPUT / 'metrics.json').write_text(json.dumps(metrics, indent=2, allow_nan=False) + '\n')
    print(json.dumps(metrics, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
