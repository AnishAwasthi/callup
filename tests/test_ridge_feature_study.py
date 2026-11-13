"""Protect paired nested comparisons, safe rates and player-level learning subsets."""
import json

import numpy as np
import pandas as pd
import pytest

from callup.modeling import fit_ridge, labeled_partitions
from callup.modeling import select_features as original_features
from callup.ridge_feature_study import (
    CONFIGURATIONS,
    PRIMARY,
    RATE_PREDICTORS,
    RATES,
    engineer_rates,
    grouped_folds,
    safe_divide,
    select_features,
    study,
    subset_indices,
    tune,
)


@pytest.fixture
def frame():
    rng = np.random.default_rng(5)
    rows = []
    for i in range(13):
        split = 'train' if i < 9 else 'test'
        available = i not in (8, 12)
        season = 2023 if split == 'train' else 2024
        rows.append(dict(player_id=100 + i, season=season, outcome_year=season + 1,
                         prediction_date=f'{season + 1}-01-01', split=split,
                         mlb_pa=100 if available else 0, mlb_woba=float(.3 + rng.normal(0, .03)) if available else np.nan,
                         label_available=available, outcome_eligible=available, reached_mlb=available,
                         label_provisional=True, outcome_status='eligible' if available else 'not_observed',
                         data_kind='synthetic', aaa_pa=200 + i * 10, aaa_ab=170 + i * 8,
                         aaa_hits=40 + i, aaa_bb=20 + i, aaa_k=50 + i, aaa_hr=5 + i,
                         ev_mean=86 + i / 3, ev_p90=102 + i / 4, ev_max=110 + i / 3,
                         hard_hit_rate=.4, la_mean=12 + i / 10, la_median=13., la_std=28.))
    rows.append({**rows[9], 'season': 2023, 'outcome_year': 2024, 'prediction_date': '2024-01-01', 'split': 'excluded_overlap'})
    return engineer_rates(pd.DataFrame(rows))


def test_safe_division_and_rate_definitions_preserve_originals(frame):
    result = safe_divide(pd.Series([0, 1, 4, np.nan]), pd.Series([0, 0, 8, 2]))
    assert result.iloc[:2].isna().all() and result.iloc[2] == .5 and pd.isna(result.iloc[3])
    with pytest.raises(ValueError, match='denominator'):
        safe_divide(pd.Series([1]), pd.Series([-1]))
    original = frame.drop(columns=RATES)
    rebuilt = engineer_rates(original)
    pd.testing.assert_frame_equal(rebuilt[original.columns], original)
    np.testing.assert_allclose(rebuilt.aaa_bb_rate, original.aaa_bb / original.aaa_pa)
    np.testing.assert_allclose(rebuilt.aaa_k_rate, original.aaa_k / original.aaa_pa)
    np.testing.assert_allclose(rebuilt.aaa_hr_rate, original.aaa_hr / original.aaa_pa)
    np.testing.assert_allclose(rebuilt.aaa_ba, original.aaa_hits / original.aaa_ab)
    zero_ab = original.copy()
    zero_ab.loc[0, 'aaa_ab'] = 0
    assert pd.isna(engineer_rates(zero_ab).loc[0, 'aaa_ba'])
    assert RATE_PREDICTORS == ['aaa_pa', 'aaa_bb_rate', 'aaa_k_rate', 'aaa_hr_rate', 'aaa_ba']
    for forbidden in ['mlb_woba', 'mlb_pa', 'season', 'player_id', 'split', 'label_available']:
        with pytest.raises(ValueError, match='allowlist'):
            select_features(frame, [forbidden])


def test_seeded_group_splits_are_reproducible_and_keep_players_together(frame):
    train, _ = labeled_partitions(frame)
    repeated = pd.concat([train, train], ignore_index=True)
    first, again, other = grouped_folds(repeated, 0), grouped_folds(repeated, 0), grouped_folds(repeated, 1)
    for (fit, valid), (fit_again, valid_again) in zip(first, again, strict=True):
        np.testing.assert_array_equal(fit, fit_again)
        np.testing.assert_array_equal(valid, valid_again)
        assert not set(repeated.iloc[fit].player_id) & set(repeated.iloc[valid].player_id)
    assert any(not np.array_equal(a[1], b[1]) for a, b in zip(first, other, strict=True))


def test_subsampling_is_by_player_and_nested_across_sizes(frame):
    train, _ = labeled_partitions(frame)
    repeated = pd.concat([train, train], ignore_index=True)
    small = repeated.iloc[subset_indices(repeated, 3, 123)]
    large = repeated.iloc[subset_indices(repeated, 5, 123)]
    assert small.player_id.nunique() == 3 and len(small) == 6
    assert set(small.player_id) <= set(large.player_id)
    np.testing.assert_array_equal(subset_indices(repeated, 3, 123), subset_indices(repeated, 3, 123))
    with pytest.raises(ValueError, match='size'):
        subset_indices(repeated, 100, 123)


def test_cached_preprocessing_reproduces_existing_ridge(frame):
    train, _ = labeled_partitions(frame)
    folds = grouped_folds(train)
    fitted, alpha, scores = tune(train, CONFIGURATIONS['counts'], folds)
    old = fit_ridge(train)
    assert alpha == old.best_params_['ridge__alpha']
    np.testing.assert_allclose(fitted.predict(original_features(train)), old.predict(original_features(train)), atol=1e-12, rtol=0)
    actual = scores.groupby('alpha').mae.mean()
    expected = -old.cv_results_['mean_test_score']
    np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=0)


def test_preprocessing_fitted_only_on_inner_fit_and_final_fit(frame, monkeypatch):
    from sklearn.impute import SimpleImputer

    train, _ = labeled_partitions(frame)
    train = train.copy()
    train.loc[train.index[0], 'aaa_ba'] = np.nan
    observed = []
    original = SimpleImputer.fit

    def record(self, X, y=None):
        observed.append(tuple(X.index))
        return original(self, X, y)

    monkeypatch.setattr(SimpleImputer, 'fit', record)
    folds = grouped_folds(train)
    pipeline, _, _ = tune(train, RATE_PREDICTORS, folds)
    assert len(observed) == len(folds) + 1
    assert observed[:-1] == [tuple(train.iloc[fit].index) for fit, _ in folds]
    assert observed[-1] == tuple(train.index)
    assert pipeline['imputer'].statistics_[-1] == train.aaa_ba.median()
    with pytest.raises(ValueError, match='overlap'):
        tune(train, RATE_PREDICTORS, [(np.arange(3), np.arange(3))])


@pytest.fixture
def small_study(frame):
    return study(frame, seeds=(-1, 0), sizes=(3,), subset_repetitions=1,
                 configurations={name: CONFIGURATIONS[name] for name in PRIMARY})


def test_pairs_baselines_subsets_and_sample_sizes(frame, small_study):
    summary, tables = small_study
    train, _ = labeled_partitions(frame)
    assert summary['n_training_players'] == 8 and summary['holdout_evaluated'] is False
    for table_name, group_columns in [('validation_predictions', ['split_seed']),
                                      ('learning_predictions', ['size_label', 'subset_repeat'])]:
        for _, group in tables[table_name].groupby(group_columns):
            base = group.loc[group.model.eq('training_average'), ['player_id', 'season', 'outer_fold', 'y_true']].reset_index(drop=True)
            assert len(base) == len(train)
            for model in PRIMARY:
                pd.testing.assert_frame_equal(base, group.loc[group.model.eq(model), base.columns].reset_index(drop=True))
    assignments = tables['fold_assignments']
    assert set(assignments.player_id) == set(train.player_id)
    for _, group in assignments.groupby(['experiment', 'split_seed', 'outer_fold', 'size_label', 'subset_repeat']):
        a = group.loc[group.role.eq('fit'), 'player_id']
        b = group.loc[group.role.eq('validation'), 'player_id']
        assert not set(a) & set(b)
    subsets = tables['subset_assignments']
    assert subsets.groupby(['outer_fold', 'subset_repeat', 'size_label']).player_id.nunique().eq(3).all()
    for row in tables['learning_fold_metrics'].loc[lambda f:f.model.eq('training_average') & f.size_label.eq('3')].itertuples():
        ids = subsets.loc[subsets.outer_fold.eq(row.outer_fold), 'player_id']
        expected = train.loc[train.player_id.isin(ids), 'mlb_woba'].mean()
        p = tables['learning_predictions']
        p = p.loc[p.model.eq('training_average') & p.size_label.eq('3') & p.outer_fold.eq(row.outer_fold)]
        np.testing.assert_allclose(p.y_pred, expected)
    baseline = tables['repetition_metrics'].loc[lambda f:f.model.eq('training_average')]
    assert baseline.delta_mae_vs_baseline.eq(0).all() and baseline.delta_rmse_vs_baseline.eq(0).all()
    json.dumps(summary, allow_nan=False)


def test_nontraining_values_cannot_change_study(frame, small_study):
    changed = frame.copy()
    mask = ~changed.split.eq('train') | ~changed.label_available
    for column in set(sum(CONFIGURATIONS.values(), [])):
        changed.loc[mask, column] = 999
    changed.loc[~changed.split.eq('train') & changed.label_available, 'mlb_woba'] = .9
    updated = study(changed, seeds=(-1, 0), sizes=(3,), subset_repetitions=1,
                    configurations={name: CONFIGURATIONS[name] for name in PRIMARY})
    assert small_study[0] == updated[0]
    for name in small_study[1]:
        pd.testing.assert_frame_equal(small_study[1][name], updated[1][name])
