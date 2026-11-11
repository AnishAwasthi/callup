"""Controlled joins, grouped tuning, missingness, leakage and frozen-benchmark checks."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from callup.contract import FEATURE_INPUTS, load
from callup.modeling import fit_ridge, labeled_partitions, select_features
from callup.ridge_ablation import (
    BATTED_PREDICTORS,
    CONFIGURATIONS,
    coverage_tables,
    experiment,
    grouped_folds,
    join_features,
    select_ablation_features,
    tune,
)
from scripts import build_batted_features as azra
from scripts import ridge_batted_ablation as cli

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def study_and_features():
    rows, features = [], []
    rng = np.random.default_rng(4)
    for i, (pid, split, available) in enumerate([
        *[(100 + i, 'train', True) for i in range(10)], (110, 'train', False),
        *[(200 + i, 'test', True) for i in range(3)], (203, 'test', False),
        (200, 'excluded_overlap', True),
    ]):
        season = 2024 if split == 'test' else 2023
        rows.append(dict(player_id=pid, name=f'Player {pid}', season=season, outcome_year=season + 1,
                         prediction_date=f'{season + 1}-01-01', split=split,
                         mlb_pa=100 if available else 0, mlb_woba=float(.3 + rng.normal(0, .03)) if available else np.nan,
                         label_available=available, outcome_eligible=available, reached_mlb=available,
                         label_provisional=True, outcome_status='eligible' if available else 'not_observed',
                         data_kind='synthetic', aaa_pa=200 + i, aaa_ab=170 + i, aaa_hits=40 + i,
                         aaa_bb=25, aaa_k=40, aaa_hr=5))
        features.append(dict(player_id=pid, season=season, ev_mean=85 + i / 3, ev_p90=100 + i / 3,
                             ev_max=110 + i / 3, hard_hit_rate=.5, la_mean=10 + i / 10,
                             la_median=11 + i / 10, la_std=28., n_bbe=100, n_ev=90, n_la=80,
                             n_hard_hit=45, ev_coverage=.9, la_coverage=.8))
    return pd.DataFrame(rows), pd.DataFrame(features)


def test_join_preserves_every_original_field_and_row(study_and_features):
    study, features = study_and_features
    joined = join_features(study, features.sample(frac=1, random_state=2))
    pd.testing.assert_frame_equal(joined[study.columns], study)
    assert len(joined) == len(study)
    assert joined.label_available.sum() == study.label_available.sum()
    assert not set(joined.loc[joined.split.eq('train'), 'player_id']) & set(joined.loc[joined.split.eq('test'), 'player_id'])
    with pytest.raises(ValueError, match='duplicate'):
        join_features(study, pd.concat([features, features.iloc[:1]]))
    with pytest.raises(ValueError, match='exactly'):
        join_features(study, features.iloc[1:])
    with pytest.raises(ValueError, match='schema'):
        join_features(study, features.assign(mlb_woba=.9))


@pytest.mark.parametrize('column,value,message', [
    ('n_ev', 101, 'exceeds'), ('n_hard_hit', -1, 'counts'), ('ev_mean', np.inf, 'Infinite'),
    ('ev_mean', np.nan, 'missingness'), ('hard_hit_rate', 0, 'inconsistent'),
    ('ev_p90', 125, 'maximum'), ('la_mean', 91, 'angle'),
])
def test_invalid_features_fail(study_and_features, column, value, message):
    study, features = study_and_features
    features.loc[0, column] = value
    with pytest.raises(ValueError, match=message):
        join_features(study, features)


def test_unmeasured_values_stay_missing_and_no_player_is_dropped(study_and_features):
    study, features = study_and_features
    features.loc[0, ['n_ev', 'n_hard_hit', 'ev_coverage']] = 0
    features.loc[0, ['ev_mean', 'ev_p90', 'ev_max', 'hard_hit_rate']] = np.nan
    joined = join_features(study, features)
    assert len(joined) == len(study) and pd.isna(joined.loc[0, 'ev_mean'])
    missing, _ = coverage_tables(joined)
    assert missing.loc[missing.group_by.eq('all') & missing.feature.eq('ev_mean'), 'n_missing'].iloc[0] == 1


def test_missing_measurement_semantics_match_azra_aggregation(monkeypatch):
    monkeypatch.setattr(azra, 'EXPECTED_STUDY_ROWS', 3)
    study = pd.DataFrame({'player_id': [1, 2, 3], 'season': [2023] * 3})
    pitches = pd.DataFrame({'batter': [1, 1, 1, 1, 2], 'season': [2023] * 5,
                           'description': ['hit_into_play'] * 3 + ['foul', 'ball'],
                           'launch_speed': [90., 100., np.nan, 125., np.nan],
                           'launch_angle': [0., 20., np.nan, 80., np.nan]})
    balls = azra.filter_batted_balls(pitches)
    features = azra.join_to_study(study, azra.summarize_batted_balls(balls), pitches)
    assert features.loc[0, 'n_bbe'] == 3
    assert features.loc[0, 'ev_mean'] == 95
    assert features.loc[0, 'ev_p90'] == 99
    assert features.loc[0, 'hard_hit_rate'] == .5
    assert features.loc[0, 'la_std'] == pytest.approx(np.std([0, 20], ddof=1))
    assert features.loc[1, 'n_bbe'] == 0 and pd.isna(features.loc[1, 'ev_mean'])
    assert pd.isna(features.loc[2, 'n_bbe'])  # No pitches differs from zero measured BBE.


def test_shared_folds_keep_repeated_players_together(study_and_features):
    study, _ = study_and_features
    train, _ = labeled_partitions(study)
    repeated = pd.concat([train, train], ignore_index=True)
    for fit, valid in grouped_folds(repeated):
        assert not set(repeated.iloc[fit].player_id) & set(repeated.iloc[valid].player_id)


def test_fold_preprocessing_uses_only_fitting_rows_and_drops_empty_columns(study_and_features, monkeypatch):
    from sklearn.impute import SimpleImputer

    study, features = study_and_features
    train, _ = labeled_partitions(join_features(study, features))
    train = train.copy()
    train['ev_max'] = np.nan
    train.loc[train.index[0], 'ev_mean'] = np.nan
    folds = grouped_folds(train)
    observed = []
    original_fit = SimpleImputer.fit

    def record_fit(self, X, y=None):
        observed.append(tuple(X.index))
        return original_fit(self, X, y)

    monkeypatch.setattr(SimpleImputer, 'fit', record_fit)
    with pytest.warns(UserWarning, match='Skipping features without any observed values'):
        search = tune(train, CONFIGURATIONS['plus_batted'], folds)
    assert len(observed) == 5 * len(folds) + 1
    assert set(observed[:-1]) == {tuple(train.iloc[fit].index) for fit, _ in folds}
    assert observed[-1] == tuple(train.index)
    pipeline = search.best_estimator_
    columns = CONFIGURATIONS['plus_batted']
    assert 'ev_max' not in pipeline['imputer'].get_feature_names_out()
    assert pipeline['imputer'].statistics_[columns.index('ev_mean')] == train.ev_mean.median()
    medians = pipeline['imputer'].statistics_.copy()
    changed = train.copy()
    changed['ev_mean'] = 10000
    with pytest.warns(UserWarning, match='Skipping features without any observed values'):
        pipeline.predict(select_ablation_features(changed, columns))
    np.testing.assert_array_equal(pipeline['imputer'].statistics_, medians)
    for forbidden in ['mlb_woba', 'player_id', 'split', 'season', 'n_ev', 'ev_coverage']:
        with pytest.raises(ValueError, match='allowlist'):
            select_ablation_features(train, [*FEATURE_INPUTS, forbidden])


def test_holdout_excluded_and_unlabeled_values_cannot_change_training(study_and_features):
    study, features = study_and_features
    frame = join_features(study, features)
    first = experiment(frame)
    changed = frame.copy()
    mask = ~changed.split.eq('train') | ~changed.label_available
    changed.loc[mask, BATTED_PREDICTORS] = 10000.
    changed.loc[~changed.split.eq('train') & changed.label_available, 'mlb_woba'] = .9
    second = experiment(changed)
    for name in CONFIGURATIONS:
        for key in ['selected_alpha', 'selection_cv_mae', 'selection_cv_rmse_mean_folds',
                    'fitted_medians', 'standardized_coefficients', 'nested_oof']:
            assert first[0]['models'][name][key] == second[0]['models'][name][key]
    for index in [2, 3, 4, 5]:
        pd.testing.assert_frame_equal(first[index], second[index])
    assert first[0]['uncertainty'] == second[0]['uncertainty']
    labels_only = frame.copy()
    labels_only.loc[labels_only.split.eq('test') & labels_only.label_available, 'mlb_woba'] = .8
    third = experiment(labels_only)
    np.testing.assert_array_equal(first[1].y_pred, third[1].y_pred)
    assert first[0]['models']['six_counts']['exploratory_holdout']['mae'] != third[0]['models']['six_counts']['exploratory_holdout']['mae']


def test_benchmark_and_paired_predictions_reproduce(study_and_features):
    study, features = study_and_features
    frame = join_features(study, features)
    metrics, predictions, folds, _, assignments, _ = experiment(frame)
    train, test = labeled_partitions(frame)
    original = fit_ridge(train)
    assert metrics['models']['six_counts']['selected_alpha'] == original.best_params_['ridge__alpha']
    assert metrics['models']['six_counts']['selection_cv_mae'] == pytest.approx(-original.best_score_)
    p = predictions.loc[predictions.evaluation.eq('exploratory_holdout') & predictions.model.eq('six_counts')]
    np.testing.assert_allclose(p.y_pred, original.predict(select_features(test)), atol=1e-12)
    for _, group in predictions.groupby('evaluation'):
        left = group.loc[group.model.eq('six_counts')].reset_index(drop=True)
        right = group.loc[group.model.eq('plus_batted')].reset_index(drop=True)
        pd.testing.assert_frame_equal(left[['player_id', 'season', 'fold', 'y_true']], right[['player_id', 'season', 'fold', 'y_true']])
        assert not left.duplicated(['player_id', 'season']).any()
    assert folds.groupby('model').n_validation.sum().to_dict() == {'six_counts': 10, 'plus_batted': 10}
    assert set(assignments.player_id) <= set(train.player_id)
    json.dumps(metrics, allow_nan=False)


def test_full_cohort_generation_and_benchmark_preserve_inputs():
    protected = [p for p in (ROOT / 'data/shared').rglob('*') if p.is_file()]
    protected += list((ROOT / 'validation/references').glob('*.json'))
    protected += [ROOT / 'data/processed/model_metrics.json', ROOT / 'data/processed/predictions.csv']
    protected = [p for p in protected if p.exists()]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    study = load(ROOT / 'data/shared/processed/hitter_seasons.csv')
    features, sources, checks, anomalies = cli.build_features(study)
    frame = join_features(study, features)
    assert len(frame) == 926 and len(checks) == 4 and len(sources) == 2
    assert len(anomalies) == 6
    assert len(anomalies[['game_pk', 'at_bat_number']].drop_duplicates()) == 3
    assert anomalies.loc[anomalies.events.isna(), ['launch_speed', 'launch_angle']].isna().all().all()
    assert frame[BATTED_PREDICTORS].notna().all().all()
    metrics, predictions, _, _, _, _ = experiment(frame)
    assert metrics['counts']['train']['labeled'] == 62
    assert metrics['counts']['test']['labeled'] == 125
    assert metrics['counts']['excluded_overlap']['labeled'] == 52
    assert cli.verify_benchmark(frame, metrics, predictions)['existing_algorithm_reproduced']
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in protected} == before
