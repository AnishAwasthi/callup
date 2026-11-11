#!/usr/bin/env python3
"""Diagnose existing training predictions and features without fitting any models."""
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

from callup.contract import load
from callup.ridge_ablation import join_features
from callup.ridge_diagnostics import MODELS, PREDICTORS, diagnostics

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/processed/ridge_limits_diagnostics_v1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_inputs(root):
    study_path = root / 'data/shared/processed/hitter_seasons.csv'
    prior = root / 'data/processed/ridge_feature_study_v1'
    features_path, predictions_path = prior / 'features_batted.csv', prior / 'validation_predictions.csv'
    for path in [features_path, predictions_path]:
        if not path.exists():
            raise FileNotFoundError(f'Restore existing saved artifact {path}; this diagnostic does not regenerate models')
    frame = join_features(load(study_path), pd.read_csv(features_path))
    train = frame.loc[frame.split.eq('train') & frame.label_available].copy()
    if len(train) != 62 or train.player_id.nunique() != 62:
        raise ValueError('Expected exactly 62 original training players')
    # Future MLB playing time and all unrelated fields are discarded before any analysis.
    train = train[['player_id', 'name', 'season', 'split', 'label_available', 'mlb_woba', *PREDICTORS]]
    saved = pd.read_csv(predictions_path)
    predictions = saved.loc[saved.split_seed.eq(-1) & saved.model.isin(MODELS)].copy()
    if not predictions.experiment.eq('validation').all() or not predictions.size_label.eq('all').all():
        raise ValueError('Existing full-fit original-split OOF predictions required')
    return train, predictions, [study_path, features_path, predictions_path]


def plot_diagnostics(tables, train, output):
    os.environ.setdefault('MPLCONFIGDIR', str(output / 'matplotlib_cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    associations = tables['outcome_associations']
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    for ax, method in zip(axes, ['pearson', 'spearman'], strict=True):
        a = associations.loc[associations.method.eq(method)]
        y = np.arange(len(a))
        value = a.correlation.to_numpy()
        ax.errorbar(value, y, xerr=np.array([value - a.lopo_min, a.lopo_max - value]), fmt='o', capsize=3)
        ax.axvline(0, color='gray', linestyle='--')
        ax.set_yticks(y, a.feature)
        ax.invert_yaxis()
        ax.set(xlabel='Correlation with provisional next-season wOBA', title=method.title())
    fig.suptitle('EXPLORATORY: 62 training players; bars = one-player omission range, not confidence intervals')
    fig.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(output / f'outcome_associations.{ext}', dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(15, 7))
    for ax, method in zip(axes, ['pearson', 'spearman'], strict=True):
        matrix = tables[f'{method}_matrix'].set_index('feature')[PREDICTORS]
        im = ax.imshow(matrix, vmin=-1, vmax=1, cmap='coolwarm')
        ax.set_xticks(range(len(PREDICTORS)), PREDICTORS, rotation=90)
        ax.set_yticks(range(len(PREDICTORS)), PREDICTORS)
        ax.set_title(method.title())
        fig.colorbar(im, ax=ax, shrink=.6)
    fig.suptitle('EXPLORATORY predictor redundancy: same 62 training players')
    fig.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(output / f'predictor_correlations.{ext}', dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
    axes[0].hist(train.mlb_woba, bins=12, color='#2867a0', alpha=.8)
    axes[0].axvline(train.mlb_woba.mean(), color='gray', linestyle='--')
    axes[0].set(xlabel='Provisional MLB wOBA', ylabel='Training players', title='Outcome distribution (n=62)')
    for model, group in tables['residuals'].groupby('model'):
        axes[1].scatter(group.y_true, group.y_pred, label=model, alpha=.65)
    limits = [train.mlb_woba.min(), train.mlb_woba.max()]
    axes[1].plot(limits, limits, color='gray', linestyle='--')
    axes[1].set(xlabel='Observed provisional wOBA', ylabel='Saved OOF prediction', title='No prediction refits')
    axes[1].legend(fontsize=8)
    for model, group in tables['ranked_errors'].groupby('model'):
        axes[2].plot(group.error_rank, group.cumulative_absolute_share, label=f'{model}: absolute')
        axes[2].plot(group.error_rank, group.cumulative_squared_share, linestyle='--', label=f'{model}: squared')
    axes[2].plot([0, len(train)], [0, 1], color='gray', linestyle=':')
    axes[2].set(xlabel='Players, largest errors first', ylabel='Cumulative error share', title='Error concentration')
    axes[2].legend(fontsize=7)
    fig.suptitle('EXPLORATORY saved original-split residuals: training players only')
    fig.tight_layout()
    for ext in ['png', 'svg']:
        fig.savefig(output / f'outcomes_and_errors.{ext}', dpi=160)
    plt.close(fig)


def main():
    if ROOT / 'data/processed' not in OUTPUT.parents:
        raise ValueError('Outputs must remain under ignored data/processed/')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    listed = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
    protected = {ROOT / p for p in listed if (ROOT / p).is_file()}
    protected.update(p for p in (ROOT / 'data/processed').rglob('*') if p.is_file() and OUTPUT not in p.parents)
    before = {str(p.relative_to(ROOT)): digest(p) for p in sorted(protected)}
    train, predictions, inputs = read_inputs(ROOT)
    summary, tables = diagnostics(train, predictions)
    summary['provenance'] = {
        'inputs_sha256': {str(p.relative_to(ROOT)): digest(p) for p in inputs},
        'code_sha256': {p: digest(ROOT / p) for p in ['callup/ridge_diagnostics.py', 'scripts/diagnose_ridge_limits.py']},
        'git_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'git_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
        'numpy_version': np.__version__, 'pandas_version': pd.__version__,
        'prediction_scope': 'Saved feature-study seed -1, counts and training_average, original full outer-fit OOF only',
    }
    for name, table in tables.items():
        table.to_csv(OUTPUT / f'{name}.csv', index=False)
    plot_diagnostics(tables, train, OUTPUT)
    changed = [p for p, h in before.items() if not (ROOT / p).is_file() or digest(ROOT / p) != h]
    if changed:
        raise ValueError(f'Previously existing file changed: {changed}')
    summary['preservation'] = {'files_verified': len(before), 'changed': []}
    (OUTPUT / 'preserved_inputs.json').write_text(json.dumps(before, indent=2) + '\n')
    (OUTPUT / 'diagnostics.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
