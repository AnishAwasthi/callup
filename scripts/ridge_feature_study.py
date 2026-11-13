#!/usr/bin/env python3
"""Run feature engineering, learning curves, contributions and split stability offline."""
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
from callup.ridge_ablation import join_features
from callup.ridge_feature_study import PRIMARY, RATES, engineer_rates, study
from scripts.ridge_batted_ablation import build_features

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/processed/ridge_feature_study_v1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_prior(root, tables):
    """Original unshuffled count configurations must reproduce committed ablation OOF."""
    path = root / 'data/processed/ridge_batted_ablation_v1/predictions.csv'
    if not path.exists():
        return {'saved_prior_available': False}
    old = pd.read_csv(path)
    old = old.loc[old.evaluation.eq('nested_training_oof')].rename(columns={'fold': 'outer_fold'})
    new = tables['validation_predictions']
    new = new.loc[new.split_seed.eq(-1) & new.model.isin(['counts', 'counts_batted'])].copy()
    new['model'] = new.model.map({'counts': 'six_counts', 'counts_batted': 'plus_batted'})
    pair = new.merge(old, on=['player_id', 'season', 'model', 'outer_fold'], validate='one_to_one', suffixes=('_new', '_old'))
    if len(pair) != len(new) or len(pair) != len(old):
        raise ValueError('Prior OOF keys differ')
    np.testing.assert_allclose(pair.y_true_new, pair.y_true_old, atol=1e-12, rtol=0)
    np.testing.assert_allclose(pair.y_pred_new, pair.y_pred_old, atol=1e-12, rtol=0)
    return {'saved_prior_available': True, 'original_nested_predictions_reproduced': True, 'source_sha256': digest(path)}


def plot_results(tables, output):
    os.environ.setdefault('MPLCONFIGDIR', str(output / 'matplotlib_cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    repetitions = tables['repetition_metrics'].loc[lambda f:f.split_seed.ne(-1)]
    learning = tables['learning_summary'].copy()
    learning['x'] = learning.size_label.map(lambda s: 49.5 if s == 'all' else float(s))
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, metric in zip(axes, ['mae', 'rmse'], strict=True):
        for model in ['training_average', *PRIMARY]:
            g = learning.loc[learning.model.eq(model)].sort_values('x')
            line, = ax.plot(g.x, g[f'mean_validation_{metric}'], marker='o', label=f'{model}: validation')
            ax.plot(g.x, g[f'mean_train_{metric}'], linestyle='--', color=line.get_color(), alpha=.5)
            sd = g[f'std_validation_{metric}'].fillna(0)
            ax.fill_between(g.x, g[f'mean_validation_{metric}'] - sd, g[f'mean_validation_{metric}'] + sd, alpha=.10, color=line.get_color())
        ax.set(xlabel='Fitting players (all = 49–50)', ylabel=metric.upper(), title='Solid validation; dashed fit; bands = subset-draw SD')
        ax.legend(fontsize=7)
    fig.suptitle('EXPLORATORY learning curves: fixed outer validation players; no holdout')
    fig.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(output / f'learning_curves.{ext}', dpi=160)
    plt.close(fig)

    order = ['training_average', *PRIMARY]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, metric in zip(axes, ['mae', 'rmse'], strict=True):
        for seed, group in repetitions.groupby('split_seed'):
            ax.plot(range(len(order)), [group.loc[group.model.eq(m), f'validation_{metric}'].iloc[0] for m in order], marker='o', label=f'Seed {seed}')
        ax.set_xticks(range(len(order)), ['Mean', 'Counts', 'Rates', 'Rates + batted'])
        ax.set(ylabel=metric.upper(), title='Same 62 players; changing grouped split assignments')
        ax.legend(fontsize=8)
    fig.suptitle('EXPLORATORY validation stability; split variation is not future-season uncertainty')
    fig.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(output / f'validation_stability.{ext}', dpi=160)
    plt.close(fig)

    contributions = tables['feature_contributions'].loc[lambda f:f.reference.eq('counts') & f.model.str.startswith('counts_')]
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    for ax, metric in zip(axes, ['mae', 'rmse'], strict=True):
        y = np.arange(len(contributions))
        mean = contributions[f'mean_delta_{metric}']
        low, high = contributions[f'min_delta_{metric}'], contributions[f'max_delta_{metric}']
        ax.errorbar(mean, y, xerr=np.array([mean - low, high - mean]), fmt='o', capsize=3)
        ax.axvline(0, color='gray', linestyle='--')
        ax.set_yticks(y, contributions.model.str.replace('counts_', '', regex=False))
        ax.set(xlabel=f'{metric.upper()} change versus counts (negative better)', title='Dots = mean; bars = range across six split seeds')
        ax.invert_yaxis()
    fig.suptitle('EXPLORATORY controlled batted-ball additions; range is not a confidence interval')
    fig.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(output / f'feature_contributions.{ext}', dpi=160)
    plt.close(fig)


def main():
    if ROOT / 'data/processed' not in OUTPUT.parents:
        raise ValueError('Output must remain under ignored data/processed/')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    listed = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
    protected = {ROOT / p for p in listed if (ROOT / p).is_file()}
    protected.update(p for p in (ROOT / 'data/processed').rglob('*') if p.is_file() and OUTPUT not in p.parents)
    before = {str(p.relative_to(ROOT)): digest(p) for p in sorted(protected)}
    source = ROOT / 'data/shared/processed/hitter_seasons.csv'
    frame = load(source)
    if len(frame) != 926:
        raise ValueError('Expected full 926-row frozen cohort')
    features, sources, checks, anomalies = build_features(frame)
    joined = engineer_rates(join_features(frame, features))
    print('Features validated; starting fixed study design', flush=True)
    summary, tables = study(joined, progress=lambda message: print(message, flush=True))
    summary['prior_comparison'] = verify_prior(ROOT, tables)
    summary['rate_coverage'] = {str(year): {p: int(g[p].isna().sum()) for p in RATES} for year, g in joined.groupby('season')}
    summary['provenance'] = {
        'study_sha256': digest(source), 'teams_sha256': digest(ROOT / 'data/shared/teams.csv'), 'pitch_sources': sources,
        'git_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'git_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
        'code_sha256': {p: digest(ROOT / p) for p in ['callup/ridge_feature_study.py', 'scripts/ridge_feature_study.py',
                        'callup/modeling.py', 'callup/ridge_ablation.py', 'scripts/ridge_batted_ablation.py', 'scripts/build_batted_features.py']},
        'versions': {'numpy': np.__version__, 'pandas': pd.__version__, 'sklearn': sklearn.__version__},
    }
    tables.update(study_with_features=joined, features_batted=features, feature_spot_checks=checks, batted_source_anomalies=anomalies)
    for name, table in tables.items():
        table.to_csv(OUTPUT / f'{name}.csv', index=False)
    plot_results(tables, OUTPUT)
    changed = [p for p, h in before.items() if not (ROOT / p).is_file() or digest(ROOT / p) != h]
    if changed:
        raise ValueError(f'Pre-existing files changed: {changed}')
    summary['preservation'] = {'verified_files': len(before), 'changed': []}
    (OUTPUT / 'preserved_inputs.json').write_text(json.dumps(before, indent=2) + '\n')
    (OUTPUT / 'metrics.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print('Completed; outputs saved under data/processed/ridge_feature_study_v1/', flush=True)


if __name__ == '__main__':
    main()
