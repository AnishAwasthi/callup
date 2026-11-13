"""Descriptive training-player diagnostics only: no estimator fitting or model selection."""
from __future__ import annotations

import numpy as np
import pandas as pd

from callup.contract import FEATURE_INPUTS
from callup.modeling import regression_metrics
from callup.ridge_ablation import BATTED_PREDICTORS

PREDICTORS = [*FEATURE_INPUTS, *BATTED_PREDICTORS]
KEYS = ['player_id', 'season']
MODELS = ['counts', 'training_average']


def correlation(x, y, method):
    """Pairwise-complete correlation; undefined results are explicit, with no p-values."""
    if method not in ['pearson', 'spearman']:
        raise ValueError('Unknown correlation method')
    paired = pd.DataFrame({'x': x, 'y': y}).dropna()
    if not np.isfinite(paired.to_numpy(dtype=float)).all():
        raise ValueError('Nonfinite correlation input')
    n = len(paired)
    if n < 3:
        return None, n, 'fewer_than_three_pairs'
    if paired.x.nunique() < 2 or paired.y.nunique() < 2:
        return None, n, 'constant_variable'
    if method == 'spearman':
        paired = paired.rank(method='average')
    return float(np.corrcoef(paired.x, paired.y)[0, 1]), n, 'available'


def associations(rows, target='mlb_woba', predictors=PREDICTORS, *, leave_one_out=False):
    if target not in ['mlb_woba', 'absolute_error'] or set(predictors) - set(PREDICTORS):
        raise ValueError('Only pre-outcome predictor associations are permitted')
    results, omitted = [], []
    for feature in predictors:
        for method in ['pearson', 'spearman']:
            value, n, status = correlation(rows[feature], rows[target], method)
            result = {'feature': feature, 'target': target, 'method': method, 'n': n,
                      'correlation': value, 'status': status}
            if leave_one_out:
                local = []
                for pid in rows.player_id.unique():
                    remaining = rows.loc[rows.player_id.ne(pid)]
                    r, count, reason = correlation(remaining[feature], remaining[target], method)
                    entry = {'feature': feature, 'method': method, 'omitted_player_id': int(pid),
                             'n_remaining': count, 'correlation': r, 'status': reason,
                             'change_from_full': None if r is None or value is None else r - value}
                    local.append(entry)
                omitted.extend(local)
                available = pd.DataFrame(local).dropna(subset=['correlation', 'change_from_full'])
                if not available.empty:
                    influential = available.loc[available.change_from_full.abs().idxmax()]
                    result.update(lopo_min=float(available.correlation.min()), lopo_max=float(available.correlation.max()),
                                  lopo_max_absolute_change=float(available.change_from_full.abs().max()),
                                  lopo_sign_flips=int(available.correlation.mul(value).lt(0).sum()),
                                  most_influential_player_id=int(influential.omitted_player_id))
            results.append(result)
    return pd.DataFrame(results), pd.DataFrame(omitted)


def predictor_diagnostics(rows):
    pairs = []
    for i, a in enumerate(PREDICTORS):
        for b in PREDICTORS[i + 1:]:
            for method in ['pearson', 'spearman']:
                value, n, status = correlation(rows[a], rows[b], method)
                pairs.append({'feature_a': a, 'feature_b': b, 'method': method, 'n': n,
                              'correlation': value, 'status': status})
    matrices = {method: rows[PREDICTORS].corr(method=method).rename_axis('feature').reset_index()
                for method in ['pearson', 'spearman']}
    blocks, vifs, singular_values = [], [], []
    for block, features in [('counts', FEATURE_INPUTS), ('batted', BATTED_PREDICTORS), ('combined', PREDICTORS)]:
        values = rows[features].dropna()
        varying = [c for c in features if values[c].nunique() > 1]
        if not varying or len(values) < 3:
            blocks.append({'block': block, 'n': len(values), 'p': len(varying), 'status': 'insufficient_varying_data'})
            continue
        z = (values[varying].to_numpy() - values[varying].mean().to_numpy()) / values[varying].std(ddof=0).to_numpy()
        _, s, vh = np.linalg.svd(z, full_matrices=False)
        rank = int(np.linalg.matrix_rank(z))
        full_rank = rank == len(varying)
        condition = float(s[0] / s[-1]) if full_rank else None
        blocks.append({'block': block, 'n': len(values), 'p': len(varying), 'rank': rank,
                       'condition_number_standardized_design': condition,
                       'first_two_squared_singular_share': float(np.square(s[:2]).sum() / np.square(s).sum()),
                       'status': 'full_rank' if full_rank else 'rank_deficient'})
        # Matrix diagnostic: diagonal inverse correlation matrix. No auxiliary regressions are fitted.
        vif = (vh.T ** 2) @ (len(values) / s ** 2) if full_rank else np.full(len(varying), np.nan)
        vifs.extend({'block': block, 'feature': feature, 'n': len(values), 'vif': float(value),
                     'status': 'available' if full_rank else 'rank_deficient'}
                    for feature, value in zip(varying, vif, strict=True))
        singular_values.extend({'block': block, 'component': i + 1, 'singular_value': float(value)} for i, value in enumerate(s))
    return pd.DataFrame(pairs), matrices, pd.DataFrame(blocks), pd.DataFrame(vifs), pd.DataFrame(singular_values)


def validate_predictions(train, predictions):
    required = [*KEYS, 'model', 'outer_fold', 'y_true', 'y_pred']
    if set(required) - set(predictions.columns) or set(predictions.model) != set(MODELS):
        raise ValueError('Two existing OOF prediction configurations required')
    if predictions.duplicated([*KEYS, 'model']).any():
        raise ValueError('Duplicate OOF prediction')
    if not np.isfinite(predictions[['y_true', 'y_pred', 'outer_fold']].to_numpy(dtype=float)).all():
        raise ValueError('Invalid OOF values')
    expected = set(map(tuple, train[KEYS].to_numpy()))
    for model, group in predictions.groupby('model'):
        if set(map(tuple, group[KEYS].to_numpy())) != expected:
            raise ValueError(f'Prediction keys differ from training cohort: {model}')
    result = predictions[required].merge(train[[*KEYS, 'name', 'mlb_woba', *PREDICTORS]],
                                         on=KEYS, validate='many_to_one')
    if not np.allclose(result.y_true, result.mlb_woba, atol=1e-12, rtol=0):
        raise ValueError('OOF target differs from frozen provisional outcome')
    a = result.loc[result.model.eq('counts'), [*KEYS, 'outer_fold']]
    b = result.loc[result.model.eq('training_average'), [*KEYS, 'outer_fold']]
    check = a.merge(b, on=KEYS, suffixes=('_ridge', '_mean'), validate='one_to_one')
    if not check.outer_fold_ridge.eq(check.outer_fold_mean).all():
        raise ValueError('Models use different validation assignments')
    baseline = result.loc[result.model.eq('training_average')]
    for _, group in baseline.groupby('outer_fold'):
        fit = train.loc[~train.player_id.isin(group.player_id)]
        if fit.empty or not np.allclose(group.y_pred, fit.mlb_woba.mean(), atol=1e-12, rtol=0):
            raise ValueError('Saved baseline is not the fold-fitted mean')
    return result


def residual_diagnostics(train, predictions):
    residuals = validate_predictions(train, predictions)
    residuals['residual'] = residuals.y_true - residuals.y_pred
    residuals['absolute_error'] = residuals.residual.abs()
    residuals['squared_error'] = residuals.residual ** 2
    summaries, concentration, cumulative, omitted, error_associations, bins = [], [], [], [], [], []
    cutpoints = train.aaa_pa.quantile([1 / 3, 2 / 3]).tolist()
    edges = [-np.inf, *sorted(set(cutpoints)), np.inf]
    for model, group in residuals.groupby('model'):
        metrics = regression_metrics(group.y_true, group.y_pred)
        ordered = group.sort_values(['absolute_error', 'player_id'], ascending=[False, True])
        total_abs, total_sq = float(group.absolute_error.sum()), float(group.squared_error.sum())
        n_half_abs = int(np.searchsorted(ordered.absolute_error.cumsum(), .5 * total_abs) + 1) if total_abs else 0
        sq_ordered = group.sort_values(['squared_error', 'player_id'], ascending=[False, True])
        n_half_sq = int(np.searchsorted(sq_ordered.squared_error.cumsum(), .5 * total_sq) + 1) if total_sq else 0
        summaries.append({'model': model, 'n': len(group), **metrics,
                          'mean_signed_residual': float(group.residual.mean()),
                          'median_absolute_error': float(group.absolute_error.median()),
                          'max_absolute_error': float(group.absolute_error.max()),
                          'prediction_sd_population': float(group.y_pred.std(ddof=0)),
                          'players_for_half_absolute_error': n_half_abs, 'players_for_half_squared_error': n_half_sq,
                          **{f'n_absolute_error_gt_{threshold}': int(group.absolute_error.gt(threshold).sum()) for threshold in [.01, .02, .05]}})
        for k in sorted({min(v, len(group)) for v in [1, 3, 5, 10, 20, len(group)]}):
            selected = ordered.head(k)
            concentration.append({'model': model, 'top_k': k, 'n': len(group),
                                  'absolute_error_share': float(selected.absolute_error.sum() / total_abs) if total_abs else None,
                                  'squared_error_share': float(selected.squared_error.sum() / total_sq) if total_sq else None})
        ranked = ordered[[*KEYS, 'name', 'y_true', 'y_pred', 'residual', 'absolute_error', 'squared_error']].copy()
        ranked['model'] = model
        ranked['error_rank'] = np.arange(1, len(ranked) + 1)
        ranked['cumulative_absolute_share'] = ranked.absolute_error.cumsum() / total_abs if total_abs else 0.
        ranked['cumulative_squared_share'] = ranked.squared_error.cumsum() / total_sq if total_sq else 0.
        cumulative.append(ranked)
        for row in group.itertuples():
            remaining = group.loc[group.player_id.ne(row.player_id)]
            score = regression_metrics(remaining.y_true, remaining.y_pred)
            omitted.append({'model': model, 'omitted_player_id': row.player_id, 'omitted_name': row.name,
                            'n_remaining': len(remaining), 'mae': score['mae'], 'rmse': score['rmse'],
                            'mae_change': score['mae'] - metrics['mae'], 'rmse_change': score['rmse'] - metrics['rmse'],
                            'note': 'Fixed saved predictions; no refit, no new LOOCV'})
        assoc, _ = associations(group, target='absolute_error')
        error_associations.append(assoc.assign(model=model))
        bucket = pd.cut(group.aaa_pa, bins=edges, include_lowest=True)
        for interval, selected in group.groupby(bucket, observed=True):
            bins.append({'model': model, 'aaa_pa_interval': str(interval), 'n': len(selected),
                         'aaa_pa_min': int(selected.aaa_pa.min()), 'aaa_pa_max': int(selected.aaa_pa.max()),
                         'mae': float(selected.absolute_error.mean()), 'rmse': float(np.sqrt(selected.squared_error.mean()))})
    omitted = pd.DataFrame(omitted)
    scores = omitted.pivot(index=['omitted_player_id', 'omitted_name'], columns='model', values=['mae', 'rmse'])
    differences = pd.DataFrame({metric + '_ridge_minus_mean': scores[metric]['counts'] - scores[metric]['training_average'] for metric in ['mae', 'rmse']}).reset_index()
    return pd.DataFrame(summaries), {
        'residuals': residuals, 'error_concentration': pd.DataFrame(concentration), 'ranked_errors': pd.concat(cumulative, ignore_index=True),
        'lopo_fixed_prediction_metrics': omitted, 'lopo_metric_differences': differences,
        'error_feature_associations': pd.concat(error_associations, ignore_index=True), 'aaa_pa_error_bins': pd.DataFrame(bins),
    }


def diagnostics(train, predictions):
    if not train.split.eq('train').all() or not train.label_available.all() or not train.season.eq(2023).all():
        raise ValueError('Diagnostics restricted to labeled training feature season 2023')
    if train.player_id.nunique() != len(train) or train.duplicated(KEYS).any():
        raise ValueError('Unique training player-season required')
    if len(train) < 4:
        raise ValueError('At least four diagnostic players required')
    if not np.isfinite(train[['mlb_woba', *PREDICTORS]].dropna().to_numpy(dtype=float)).all():
        raise ValueError('Nonfinite training value')
    assoc, lopo = associations(train, leave_one_out=True)
    pairs, matrices, blocks, vifs, singular = predictor_diagnostics(train)
    errors, tables = residual_diagnostics(train, predictions)
    outcome = {'n': len(train), 'mean': float(train.mlb_woba.mean()),
               'std_sample': float(train.mlb_woba.std(ddof=1)), 'std_population': float(train.mlb_woba.std(ddof=0)),
               'quantiles': {str(q): float(train.mlb_woba.quantile(q)) for q in [0, .05, .1, .25, .5, .75, .9, .95, 1]}}
    outcome_lopo = pd.DataFrame([{'omitted_player_id': int(pid), 'remaining_mean': float(train.loc[train.player_id.ne(pid), 'mlb_woba'].mean())}
                                 for pid in train.player_id])
    outcome_lopo['change_from_full_mean'] = outcome_lopo.remaining_mean - outcome['mean']
    import json
    summary = {'diagnostic_only': True, 'models_fitted': 0, 'hyperparameter_searches': 0, 'holdout_evaluated': False,
               'outcome_distribution': outcome, 'associations': json.loads(assoc.to_json(orient='records', double_precision=15)),
               'collinearity': json.loads(blocks.to_json(orient='records', double_precision=15)),
               'residual_summary': json.loads(errors.to_json(orient='records', double_precision=15)),
               'definitions': {'residual': 'Observed provisional outcome minus saved OOF prediction',
                               'lopo': 'Descriptive omission of one player; no prediction refits or cohort edits',
                               'vif': 'Diagonal inverse predictor correlation matrix from SVD; not auxiliary regression fits',
                               'aaa_pa_bins': 'Training AAA PA tertile boundaries; fixed descriptive groups'},
               'limits': ['Same 62 previously studied training players; no independent confirmation or causal claims.',
                          'No p-values or model/feature selection; correlations and error relationships are exploratory.',
                          'Fixed-prediction omission does not estimate how a refitted model would change.']}
    tables.update(outcome_associations=assoc, lopo_associations=lopo, predictor_pairs=pairs, pearson_matrix=matrices['pearson'],
                  spearman_matrix=matrices['spearman'], collinearity_blocks=blocks, collinearity_vif=vifs,
                  singular_values=singular, residual_summary=errors, lopo_outcome_mean=outcome_lopo)
    return summary, tables
