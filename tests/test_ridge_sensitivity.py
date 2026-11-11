"""Regression paths must preserve paired players, fold-local preprocessing and old results."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from callup.contract import load
from callup.modeling import RIDGE_ALPHAS, labeled_partitions
from callup.ridge_ablation import CONFIGURATIONS, grouped_folds, join_features
from callup.ridge_sensitivity import (
    WIDE_ALPHAS,
    alpha_path,
    boundary,
    choose_alpha,
    fit_at_alpha,
    sensitivity,
    validate_grid,
)
from scripts.ridge_regularization_sensitivity import compare_saved

ROOT = Path(__file__).resolve().parents[1]
SMALL_GRID = (.001, *RIDGE_ALPHAS, 100000.)


@pytest.fixture
def frame():
    rng = np.random.default_rng(7)
    rows = []
    for i in range(16):
        split = 'train' if i < 11 else 'test'
        season = 2023 if split == 'train' else 2024
        available = i not in (10, 15)
        signal = float(rng.normal())
        rows.append(dict(player_id=100 + i, season=season, outcome_year=season + 1,
                         prediction_date=f'{season + 1}-01-01', split=split,
                         mlb_pa=100 if available else 0,
                         mlb_woba=.3 + .02 * signal + float(rng.normal(0, .01)) if available else np.nan,
                         label_available=available, outcome_eligible=available, reached_mlb=available,
                         label_provisional=True, outcome_status='eligible' if available else 'not_observed',
                         data_kind='synthetic', aaa_pa=250, aaa_ab=220, aaa_hits=round(60 + 10 * signal),
                         aaa_bb=25, aaa_k=50, aaa_hr=10,
                         ev_mean=89 + signal, ev_p90=103 + signal, ev_max=111 + signal,
                         hard_hit_rate=.4 + .03 * signal, la_mean=12 + signal,
                         la_median=13 + signal, la_std=28 + signal))
    rows.append({**rows[11], 'season': 2023, 'outcome_year': 2024,
                 'prediction_date': '2024-01-01', 'split': 'excluded_overlap'})
    return pd.DataFrame(rows)


def test_grid_bounds_original_values_and_bad_grids():
    assert len(WIDE_ALPHAS) == 17
    assert WIDE_ALPHAS[0] == .001 and WIDE_ALPHAS[-1] == 100000
    assert set(RIDGE_ALPHAS) <= set(WIDE_ALPHAS)
    for bad in [[], [0], [-1], [np.nan], [np.inf], [1, 1], [10, 1]]:
        with pytest.raises(ValueError, match='grid'):
            validate_grid(bad)
    assert boundary(.001, WIDE_ALPHAS) == 'lower'
    assert boundary(100000, WIDE_ALPHAS) == 'upper'
    assert boundary(100, WIDE_ALPHAS) == 'interior'


def test_selection_is_fold_mean_mae_and_ties_choose_ascending_alpha():
    scores = pd.DataFrame({'alpha': [1, 1, 10, 10], 'validation_mae': [1., 3., 2., 2.],
                           'validation_rmse': [9, 9, 1, 1]})
    assert choose_alpha(scores, [1, 10]) == 1
    with pytest.raises(ValueError, match='Missing'):
        choose_alpha(scores, [1, 10, 100])


def test_stronger_penalty_reduces_coefficients_and_increases_fit_mse(frame):
    train, _ = labeled_partitions(frame)
    folds = grouped_folds(train)
    stats, coefficients, predictions = alpha_path(train, CONFIGURATIONS['plus_batted'], folds,
                                                  SMALL_GRID, model='plus_batted', scope='test')
    for _, group in stats.groupby('fold'):
        group = group.sort_values('alpha')
        assert np.all(np.diff(group.coefficient_l2) <= 1e-12)
        assert np.all(np.diff(group.train_rmse) >= -1e-12)
        np.testing.assert_allclose(group.gap_mae, group.validation_mae - group.train_mae)
        np.testing.assert_allclose(group.validation_prediction_variance, group.validation_prediction_sd ** 2)
    assert set(coefficients.predictor) <= set(CONFIGURATIONS['plus_batted'])
    assert len(predictions) == len(train) * len(SMALL_GRID)
    fitted = fit_at_alpha(train, CONFIGURATIONS['six_counts'], 1e9)
    actual = fitted.predict(train[CONFIGURATIONS['six_counts']])
    np.testing.assert_allclose(actual, train.mlb_woba.mean(), atol=1e-8)


def test_path_preprocessing_is_fold_local(frame, monkeypatch):
    from sklearn.impute import SimpleImputer

    train, _ = labeled_partitions(frame)
    train = train.copy()
    train.loc[train.index[0], 'ev_mean'] = np.nan
    folds = grouped_folds(train)
    seen = []
    original = SimpleImputer.fit

    def record(self, X, y=None):
        seen.append(tuple(X.index))
        return original(self, X, y)

    monkeypatch.setattr(SimpleImputer, 'fit', record)
    alpha_path(train, CONFIGURATIONS['plus_batted'], folds, [1, 100], model='plus_batted', scope='test')
    assert len(seen) == 2 * len(folds)
    assert set(seen) == {tuple(train.iloc[fit].index) for fit, _ in folds}
    assert tuple(train.index) not in seen
    with pytest.raises(ValueError, match='overlap'):
        alpha_path(train, CONFIGURATIONS['six_counts'], [(np.arange(5), np.arange(5))],
                   [1], model='six_counts', scope='test')


def test_nontraining_data_cannot_change_any_sensitivity_result(frame):
    first, tables = sensitivity(frame, SMALL_GRID)
    changed = frame.copy()
    nontraining = ~changed.split.eq('train') | ~changed.label_available
    for columns in CONFIGURATIONS.values():
        # Starter counts stay valid integers; batted columns may change independently.
        changed.loc[nontraining, columns] = 999
    changed.loc[~changed.split.eq('train') & changed.label_available, 'mlb_woba'] = .9
    second, changed_tables = sensitivity(changed, SMALL_GRID)
    assert first == second
    for name in tables:
        pd.testing.assert_frame_equal(tables[name], changed_tables[name])
    assert first['test_evaluated'] is False
    assert first['n_training_rows'] == 10
    json.dumps(first, allow_nan=False)


def test_mean_baseline_and_all_procedures_use_identical_outer_players(frame):
    summary, tables = sensitivity(frame, SMALL_GRID)
    train, _ = labeled_partitions(frame)
    train = train.reset_index(drop=True)
    predictions = tables['nested_predictions']
    baseline = predictions.loc[predictions.procedure.eq('baseline')]
    for fold, (fit, valid) in enumerate(grouped_folds(train)):
        selected = baseline.loc[baseline.fold.eq(fold)]
        assert selected.player_id.tolist() == train.iloc[valid].player_id.tolist()
        np.testing.assert_allclose(selected.y_pred, train.iloc[fit].mlb_woba.mean())
    keys = baseline[['player_id', 'season', 'fold', 'y_true']].reset_index(drop=True)
    for (_, _), group in predictions.groupby(['model', 'procedure']):
        pd.testing.assert_frame_equal(group[['player_id', 'season', 'fold', 'y_true']].reset_index(drop=True), keys)
    assert set(tables['fold_assignments'].player_id) == set(train.player_id)
    assert len(summary['nested_results']) == 5
    assert len(tables['paired_fold_differences']) == 20
    assert all(r['n'] == len(train) for r in summary['nested_results'])


def test_full_cohort_matches_saved_ablation_without_test_prediction():
    study = load(ROOT / 'data/shared/processed/hitter_seasons.csv')
    saved = ROOT / 'data/processed/ridge_batted_ablation_v1/features_batted.csv'
    if saved.exists():
        features = pd.read_csv(saved)
    else:
        from scripts.ridge_batted_ablation import build_features
        features, _, _, _ = build_features(study)
    summary, tables = sensitivity(join_features(study, features), SMALL_GRID)
    assert summary['n_training_players'] == 62
    comparison = compare_saved(ROOT, summary, tables)
    if 'previous_ablation' in comparison:
        assert comparison['previous_ablation']['old_grid_nested_predictions_reproduced']
        assert comparison['previous_ablation']['identical_saved_fold_assignments']
    assert len(tables['nested_predictions']) == 5 * 62
    assert tables['nested_predictions'].season.eq(2023).all()
    assert tables['fold_assignments'].season.eq(2023).all()
