#!/usr/bin/env python3
"""Explore Ridge regularization using training players only; preserve prior experiments."""
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
from callup.ridge_sensitivity import sensitivity
from scripts.ridge_batted_ablation import build_features

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/processed/ridge_regularization_sensitivity_v1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_saved(root, summary, tables):
    """Verify old-grid nested results against saved ablation; archive old holdout context only."""
    result = {'note': 'Saved holdout numbers are historical context only; no new test predictions or scores calculated.'}
    prior = root / 'data/processed/ridge_batted_ablation_v1'
    if (prior / 'metrics.json').exists() and (prior / 'predictions.csv').exists():
        old_metrics = json.loads((prior / 'metrics.json').read_text())
        old_predictions = pd.read_csv(prior / 'predictions.csv')
        old_predictions = old_predictions.loc[old_predictions.evaluation.eq('nested_training_oof')]
        new = tables['nested_predictions'].loc[lambda f:f.procedure.eq('original_grid')]
        paired = new.merge(old_predictions, on=['player_id', 'season', 'fold', 'model'],
                           suffixes=('_new', '_old'), validate='one_to_one')
        if len(paired) != len(new) or len(paired) != len(old_predictions):
            raise ValueError('Saved original-grid prediction keys differ')
        np.testing.assert_allclose(paired.y_true_new, paired.y_true_old, atol=1e-12, rtol=0)
        np.testing.assert_allclose(paired.y_pred_new, paired.y_pred_old, atol=1e-12, rtol=0)
        for model in ['six_counts', 'plus_batted']:
            if summary['final_training_selection'][model]['original_grid']['alpha'] != old_metrics['models'][model]['selected_alpha']:
                raise ValueError('Saved original-grid alpha differs')
            recomputed = next(r for r in summary['nested_results'] if r['model'] == model and r['procedure'] == 'original_grid')
            for metric in ['mae', 'rmse']:
                np.testing.assert_allclose(recomputed[metric], old_metrics['models'][model]['nested_oof'][metric], atol=1e-12, rtol=0)
        if (prior / 'fold_assignments.csv').exists():
            pd.testing.assert_frame_equal(tables['fold_assignments'], pd.read_csv(prior / 'fold_assignments.csv'))
        result['previous_ablation'] = {
            'old_grid_nested_predictions_reproduced': True,
            'identical_saved_fold_assignments': (prior / 'fold_assignments.csv').exists(),
            'metrics_sha256': digest(prior / 'metrics.json'), 'predictions_sha256': digest(prior / 'predictions.csv'),
            'saved_models': {model: {k: v for k, v in m.items() if k in ['selected_alpha', 'nested_oof', 'exploratory_holdout']}
                             for model, m in old_metrics['models'].items()},
        }
    baseline_path = root / 'data/processed/model_metrics.json'
    if baseline_path.exists():
        saved = json.loads(baseline_path.read_text())
        result['initial_benchmark'] = {'sha256': digest(baseline_path), 'saved_holdout_only': {
            model: {k: v for k, v in m.items() if k in ['selected_alpha', 'training_mean', 'mae', 'rmse', 'r2']}
            for model, m in saved['models'].items()}}
    return result


def plot_results(tables, output):
    os.environ.setdefault('MPLCONFIGDIR', str(output / 'matplotlib_cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    curves = tables['alpha_summary']
    nested = tables['nested_fold_metrics']
    baseline = nested.loc[nested.model.eq('training_average')]
    fig, axes = plt.subplots(2, 4, figsize=(18, 8))
    for row, model in enumerate(['six_counts', 'plus_batted']):
        c = curves.loc[curves.model.eq(model)].sort_values('alpha')
        for column, metric in enumerate(['mae', 'rmse']):
            ax = axes[row, column]
            ax.plot(c.alpha, c[f'mean_train_{metric}'], label='Fit error')
            ax.plot(c.alpha, c[f'mean_validation_{metric}'], label='Validation error')
            ax.fill_between(c.alpha, c[f'mean_validation_{metric}'] - c[f'std_validation_{metric}'],
                            c[f'mean_validation_{metric}'] + c[f'std_validation_{metric}'], alpha=.15,
                            label='Validation ±1 fold SD')
            ax.axhline(baseline[metric].mean(), color='gray', linestyle='--', label='Fold-fit training mean')
            ax.set(xscale='log', xlabel='Alpha', ylabel=metric.upper(), title=f'{model}: {metric.upper()}')
            ax.legend(fontsize=7)
        axes[row, 2].plot(c.alpha, c.mean_coefficient_l2)
        axes[row, 2].set(xscale='log', yscale='log', xlabel='Alpha', ylabel='Mean L2 norm', title=f'{model}: standardized coefficients')
        axes[row, 3].plot(c.alpha, c.mean_train_prediction_sd, label='Fit prediction SD')
        axes[row, 3].plot(c.alpha, c.mean_validation_prediction_sd, label='Validation prediction SD')
        axes[row, 3].set(xscale='log', xlabel='Alpha', ylabel='Prediction SD', title=f'{model}: within-fold spread')
        axes[row, 3].legend(fontsize=7)
    fig.suptitle('EXPLORATORY: fixed-alpha paths on training players; shaded folds are not independent')
    fig.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(output / f'regularization_paths.{ext}', dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    order = [('training_average', 'baseline'), ('six_counts', 'original_grid'), ('six_counts', 'wide_grid'),
             ('plus_batted', 'original_grid'), ('plus_batted', 'wide_grid')]
    labels = ['Training\nmean', 'Six\nold grid', 'Six\nwide grid', 'Thirteen\nold grid', 'Thirteen\nwide grid']
    for ax, metric in zip(axes, ['mae', 'rmse'], strict=True):
        for fold in sorted(nested.fold.unique()):
            values = [nested.loc[nested.model.eq(model) & nested.procedure.eq(procedure) & nested.fold.eq(fold), metric].iloc[0] for model, procedure in order]
            ax.plot(range(len(order)), values, marker='o', alpha=.6, label=f'Fold {fold + 1}')
        ax.set_xticks(range(len(order)), labels)
        ax.set(ylabel=metric.upper(), title=f'Nested outer-fold {metric.upper()}')
        ax.legend(fontsize=8)
    fig.suptitle('EXPLORATORY: same 62 training players; no holdout evaluation')
    fig.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(output / f'nested_comparison.{ext}', dpi=160)
    plt.close(fig)


def main():
    if ROOT / 'data/processed' not in OUTPUT.parents:
        raise ValueError('Output must be under ignored data/processed/')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    tracked = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
    protected = {ROOT / p for p in tracked if (ROOT / p).is_file()}
    protected.update(p for p in (ROOT / 'data/processed').rglob('*') if p.is_file() and OUTPUT not in p.parents)
    before = {str(p.relative_to(ROOT)): digest(p) for p in sorted(protected)}
    study_path = ROOT / 'data/shared/processed/hitter_seasons.csv'
    study = load(study_path)
    if len(study) != 926:
        raise ValueError('Expected 926 frozen study rows')
    features, sources, spot_checks, anomalies = build_features(study)
    frame = join_features(study, features)
    summary, tables = sensitivity(frame)
    # Comparison is read only and follows all training-only selection.
    summary['saved_comparison'] = compare_saved(ROOT, summary, tables)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip())
    summary['provenance'] = {
        'study_sha256': digest(study_path), 'sources': sources,
        'teams_sha256': digest(ROOT / 'data/shared/teams.csv'), 'git_revision': revision, 'git_dirty': dirty,
        'code_sha256': {p: digest(ROOT / p) for p in ['callup/ridge_sensitivity.py', 'scripts/ridge_regularization_sensitivity.py',
                                                     'callup/modeling.py', 'callup/ridge_ablation.py', 'scripts/ridge_batted_ablation.py', 'scripts/build_batted_features.py']},
        'versions': {'numpy': np.__version__, 'pandas': pd.__version__, 'sklearn': sklearn.__version__},
    }
    tables.update(features_batted=features, feature_spot_checks=spot_checks, batted_source_anomalies=anomalies)
    for name, table in tables.items():
        table.to_csv(OUTPUT / f'{name}.csv', index=False)
    plot_results(tables, OUTPUT)
    changed = [p for p, h in before.items() if not (ROOT / p).is_file() or digest(ROOT / p) != h]
    if changed:
        raise ValueError(f'Protected files changed: {changed}')
    summary['preservation'] = {'files_verified': len(before), 'changed': []}
    (OUTPUT / 'preserved_inputs.json').write_text(json.dumps(before, indent=2) + '\n')
    (OUTPUT / 'metrics.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
