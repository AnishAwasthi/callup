"""Diagnostics must reuse predictions, reject leakage, and make omissions explicit."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from callup.ridge_diagnostics import (
    PREDICTORS,
    associations,
    correlation,
    diagnostics,
    predictor_diagnostics,
    validate_predictions,
)
from scripts.diagnose_ridge_limits import read_inputs

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def diagnostic_data():
    n = 6
    train = pd.DataFrame({'player_id': range(1, n + 1), 'name': [f'Player {i}' for i in range(1, n + 1)],
                          'season': 2023, 'split': 'train', 'label_available': True,
                          'mlb_woba': [.2, .25, .3, .31, .35, .4]})
    for i, column in enumerate(PREDICTORS):
        train[column] = np.arange(n, dtype=float) + i + 1
    train['aaa_pa'] = [150, 200, 250, 300, 350, 400]
    predictions = []
    for i, row in train.iterrows():
        fold = i % 3
        mean = train.loc[train.index % 3 != fold, 'mlb_woba'].mean()
        for model, value in [('training_average', mean), ('counts', mean + .001 * (i - 2))]:
            predictions.append({'player_id': row.player_id, 'season': row.season, 'model': model,
                                'outer_fold': fold, 'y_true': row.mlb_woba, 'y_pred': value})
    return train, pd.DataFrame(predictions)


def test_correlations_ties_missingness_and_undefined_values():
    x, y = pd.Series([1, 1, 3, 4]), pd.Series([1, 2, 3, 4])
    value, n, status = correlation(x, y, 'spearman')
    assert n == 4 and status == 'available'
    assert value == pytest.approx(x.rank().corr(y.rank()))
    assert correlation(pd.Series([1, 2, 3, np.nan]), pd.Series([2, 4, 6, 8]), 'pearson')[:2] == (1., 3)
    assert correlation(pd.Series([1, 1, 1]), pd.Series([1, 2, 3]), 'pearson') == (None, 3, 'constant_variable')
    assert correlation(pd.Series([1, 2]), pd.Series([2, 3]), 'pearson')[2] == 'fewer_than_three_pairs'
    with pytest.raises(ValueError, match='Nonfinite'):
        correlation(pd.Series([1, 2, np.inf]), pd.Series([1, 2, 3]), 'pearson')


def test_lopo_removes_one_player_without_changing_original(diagnostic_data):
    train, _ = diagnostic_data
    before = train.copy(deep=True)
    summary, omitted = associations(train, leave_one_out=True)
    assert len(summary) == 2 * len(PREDICTORS)
    assert len(omitted) == len(train) * len(summary)
    assert omitted.n_remaining.eq(len(train) - 1).all()
    for row in omitted.loc[omitted.feature.eq('aaa_pa') & omitted.method.eq('pearson')].itertuples():
        remaining = train.loc[train.player_id.ne(row.omitted_player_id)]
        expected = remaining.aaa_pa.corr(remaining.mlb_woba)
        assert row.correlation == pytest.approx(expected)
    pd.testing.assert_frame_equal(train, before)
    for future in ['mlb_pa', 'outcome_year', 'label_available']:
        with pytest.raises(ValueError, match='pre-outcome'):
            associations(train, predictors=[future])
    with pytest.raises(ValueError, match='pre-outcome'):
        associations(train, target='mlb_pa')


def test_collinearity_is_matrix_only_and_rank_deficiency_is_explicit(diagnostic_data):
    train, _ = diagnostic_data
    pairs, _, blocks, vifs, _ = predictor_diagnostics(train)
    assert len(pairs) == len(PREDICTORS) * (len(PREDICTORS) - 1)
    assert blocks.status.eq('rank_deficient').all()
    assert vifs.vif.isna().all()
    # A larger full-rank synthetic matrix has VIF = diagonal inverse correlation.
    independent = pd.DataFrame()
    rng = np.random.default_rng(1)
    for feature in PREDICTORS:
        independent[feature] = rng.normal(size=100)
    _, _, blocks, vifs, _ = predictor_diagnostics(independent)
    assert blocks.status.eq('full_rank').all()
    expected = np.diag(np.linalg.inv(independent[PREDICTORS].corr().to_numpy()))
    np.testing.assert_allclose(vifs.loc[vifs.block.eq('combined'), 'vif'], expected, atol=1e-12)


def test_saved_prediction_integrity_checks(diagnostic_data):
    train, predictions = diagnostic_data
    validate_predictions(train, predictions)
    for wrong in [predictions.iloc[:-1], pd.concat([predictions, predictions.iloc[:1]])]:
        with pytest.raises(ValueError):
            validate_predictions(train, wrong)
    changed = predictions.copy()
    changed.loc[0, 'y_true'] += .01
    with pytest.raises(ValueError, match='target'):
        validate_predictions(train, changed)
    changed = predictions.copy()
    changed.loc[changed.model.eq('counts') & changed.player_id.eq(1), 'outer_fold'] = 99
    with pytest.raises(ValueError, match='assignments'):
        validate_predictions(train, changed)
    changed = predictions.copy()
    changed.loc[changed.model.eq('training_average'), 'y_pred'] += .01
    with pytest.raises(ValueError, match='fold-fitted'):
        validate_predictions(train, changed)


def test_residual_concentration_and_fixed_prediction_omissions(diagnostic_data):
    train, predictions = diagnostic_data
    summary, tables = diagnostics(train, predictions)
    assert summary['models_fitted'] == summary['hyperparameter_searches'] == 0
    assert summary['holdout_evaluated'] is False
    for model, residuals in tables['residuals'].groupby('model'):
        np.testing.assert_allclose(residuals.residual, residuals.y_true - residuals.y_pred)
        np.testing.assert_allclose(residuals.squared_error, residuals.absolute_error ** 2)
        concentration = tables['error_concentration']
        concentration = concentration.loc[concentration.model.eq(model)]
        assert concentration.iloc[-1].absolute_error_share == pytest.approx(1)
        assert concentration.iloc[-1].squared_error_share == pytest.approx(1)
        omitted = tables['lopo_fixed_prediction_metrics']
        for row in omitted.loc[omitted.model.eq(model)].itertuples():
            remaining = residuals.loc[residuals.player_id.ne(row.omitted_player_id)]
            assert row.mae == pytest.approx(remaining.absolute_error.mean())
            assert row.rmse == pytest.approx(np.sqrt(remaining.squared_error.mean()))
    assert tables['aaa_pa_error_bins'].groupby('model').n.sum().eq(len(train)).all()
    assert set(tables['error_feature_associations'].feature) == set(PREDICTORS)
    json.dumps(summary, allow_nan=False)
    changed = train.copy()
    changed['mlb_pa'] = 999999  # Not selected, associated or emitted.
    again, again_tables = diagnostics(changed, predictions)
    assert summary == again
    for name in tables:
        pd.testing.assert_frame_equal(tables[name], again_tables[name])


def test_nontraining_and_duplicate_players_are_rejected(diagnostic_data):
    train, predictions = diagnostic_data
    with pytest.raises(ValueError, match='restricted'):
        diagnostics(train.assign(split='test'), predictions)
    with pytest.raises(ValueError, match='Unique'):
        diagnostics(pd.concat([train, train.iloc[:1]]), predictions)


def test_real_inputs_no_estimator_fit_or_future_playing_time(monkeypatch):
    if not all((ROOT / f'data/processed/ridge_feature_study_v1/{name}').exists() for name in ['features_batted.csv', 'validation_predictions.csv']):
        pytest.skip('Diagnostic integration requires the existing ignored feature-study artifacts; never regenerate models in this test')
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import GridSearchCV

    def forbidden(*args, **kwargs):
        raise AssertionError('No model fitting permitted in diagnostics')

    monkeypatch.setattr(Ridge, 'fit', forbidden)
    monkeypatch.setattr(GridSearchCV, 'fit', forbidden)
    train, predictions, _ = read_inputs(ROOT)
    assert len(train) == train.player_id.nunique() == 62
    assert 'mlb_pa' not in train.columns
    summary, tables = diagnostics(train, predictions)
    assert summary['outcome_distribution']['n'] == 62
    assert tables['outcome_associations'].n.eq(62).all()
    assert tables['lopo_associations'].n_remaining.eq(61).all()
    assert len(tables['residuals']) == 124
    assert summary['models_fitted'] == 0
