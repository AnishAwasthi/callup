"""Training-only Ridge paths and nested sensitivity to the alpha search range."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer

from callup.modeling import RIDGE_ALPHAS, labeled_partitions, regression_metrics, ridge_pipeline
from callup.ridge_ablation import CONFIGURATIONS, grouped_folds, select_ablation_features, spread

WIDE_ALPHAS = tuple(10.0 ** (i / 2) for i in range(-6, 11))


def validate_grid(alphas):
    grid = tuple(float(a) for a in alphas)
    if not grid or not all(np.isfinite(a) and a > 0 for a in grid) or tuple(sorted(set(grid))) != grid:
        raise ValueError('Alpha grid must be positive, finite, unique and increasing')
    return grid


def fit_at_alpha(train, predictors, alpha):
    validate_grid([alpha])
    pipeline = ridge_pipeline()
    pipeline.set_params(imputer=SimpleImputer(strategy='median', keep_empty_features=False), ridge__alpha=alpha)
    pipeline.fit(select_ablation_features(train, predictors), train.mlb_woba)
    return pipeline


def fit_diagnostics(pipeline, fitting, validation, predictors):
    train_pred = pipeline.predict(select_ablation_features(fitting, predictors))
    valid_pred = pipeline.predict(select_ablation_features(validation, predictors))
    train_metrics = regression_metrics(fitting.mlb_woba, train_pred)
    valid_metrics = regression_metrics(validation.mlb_woba, valid_pred)
    beta = pipeline['ridge'].coef_
    stats = {'n_fit': len(fitting), 'n_validation': len(validation),
             **{f'train_{k}': v for k, v in train_metrics.items() if k in ['mae', 'rmse']},
             **{f'validation_{k}': v for k, v in valid_metrics.items() if k in ['mae', 'rmse']},
             'coefficient_l2': float(np.linalg.norm(beta)), 'coefficient_l1': float(np.abs(beta).sum()),
             'coefficient_max_abs': float(np.abs(beta).max()),
             'train_prediction_variance': float(np.var(train_pred)),
             'validation_prediction_variance': float(np.var(valid_pred)),
             'train_prediction_sd': float(np.std(train_pred)),
             'validation_prediction_sd': float(np.std(valid_pred)),
             'train_outcome_sd': float(np.std(fitting.mlb_woba)),
             'validation_outcome_sd': float(np.std(validation.mlb_woba)),
             'intercept': float(pipeline['ridge'].intercept_)}
    for metric in ['mae', 'rmse']:
        stats[f'gap_{metric}'] = stats[f'validation_{metric}'] - stats[f'train_{metric}']
    return stats, valid_pred


def alpha_path(rows, predictors, folds, alphas, *, model, scope, save_predictions=True):
    """Every alpha/fold fit learns preprocessing only from that fold's fitting rows."""
    grid = validate_grid(alphas)
    metrics, predictions, coefficients = [], [], []
    for fold, (fit, valid) in enumerate(folds):
        fitting, validation = rows.iloc[fit], rows.iloc[valid]
        if set(fitting.player_id) & set(validation.player_id):
            raise ValueError('Player overlap in validation fold')
        for alpha in grid:
            pipeline = fit_at_alpha(fitting, predictors, alpha)
            stats, values = fit_diagnostics(pipeline, fitting, validation, predictors)
            identity = dict(model=model, scope=scope, fold=fold, alpha=alpha)
            metrics.append({**identity, **stats})
            for feature, coefficient in zip(pipeline['imputer'].get_feature_names_out(), pipeline['ridge'].coef_, strict=True):
                coefficients.append({**identity, 'predictor': feature, 'standardized_coefficient': float(coefficient)})
            if save_predictions:
                p = validation[['player_id', 'season', 'mlb_woba']].rename(columns={'mlb_woba': 'y_true'}).copy()
                predictions.append(p.assign(**identity, y_pred=values))
    return pd.DataFrame(metrics), pd.DataFrame(coefficients), pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()


def choose_alpha(scores, grid):
    """Minimum unweighted mean fold MAE; ascending-grid tie break matches existing selection."""
    grid = validate_grid(grid)
    means = scores.loc[scores.alpha.isin(grid)].groupby('alpha').validation_mae.mean()
    if set(means.index) != set(grid):
        raise ValueError('Missing alpha scores')
    return float(means.reindex(grid).idxmin())


def boundary(alpha, grid):
    if alpha == grid[0]:
        return 'lower'
    if alpha == grid[-1]:
        return 'upper'
    return 'interior'


def curve_summary(scores, predictions):
    records = []
    for (model, alpha), group in scores.groupby(['model', 'alpha']):
        row = {'model': model, 'alpha': alpha}
        for c in ['train_mae', 'train_rmse', 'validation_mae', 'validation_rmse', 'gap_mae', 'gap_rmse',
                  'coefficient_l2', 'coefficient_l1', 'coefficient_max_abs', 'train_prediction_variance',
                  'validation_prediction_variance', 'train_prediction_sd', 'validation_prediction_sd']:
            row[f'mean_{c}'] = float(group[c].mean())
            row[f'std_{c}'] = float(group[c].std())
        p = predictions.loc[predictions.model.eq(model) & predictions.alpha.eq(alpha)]
        row.update({f'pooled_validation_{k}': v for k, v in regression_metrics(p.y_true, p.y_pred).items()})
        row['pooled_prediction_sd'] = float(p.y_pred.std(ddof=0))
        records.append(row)
    return pd.DataFrame(records)


def paired_changes(predictions):
    """Compare nested wide-grid predictions with old-grid tuning and the fold-fitted mean."""
    rows = []
    for model in CONFIGURATIONS:
        expanded = predictions.loc[predictions.model.eq(model) & predictions.procedure.eq('wide_grid')]
        for comparator_model, comparator in [(model, 'original_grid'), ('training_average', 'baseline')]:
            other = predictions.loc[predictions.model.eq(comparator_model) & predictions.procedure.eq(comparator)]
            paired = expanded.merge(other, on=['player_id', 'season', 'fold'], suffixes=('_wide', '_other'), validate='one_to_one')
            if len(paired) != len(expanded) or not np.array_equal(paired.y_true_wide, paired.y_true_other):
                raise ValueError('Paired observations differ')
            for fold, group in paired.groupby('fold'):
                w = regression_metrics(group.y_true_wide, group.y_pred_wide)
                o = regression_metrics(group.y_true_other, group.y_pred_other)
                rows.append({'model': model, 'comparator': comparator, 'fold': fold, 'n': len(group),
                             'delta_mae_wide_minus_other': w['mae'] - o['mae'],
                             'delta_rmse_wide_minus_other': w['rmse'] - o['rmse']})
    return pd.DataFrame(rows)


def sensitivity(frame, alphas=WIDE_ALPHAS):
    grid = validate_grid(alphas)
    if not set(RIDGE_ALPHAS) <= set(grid):
        raise ValueError('Wide grid must include all original alpha values')
    train, _ = labeled_partitions(frame)
    train = train.reset_index(drop=True)
    if train.player_id.nunique() < 3:
        raise ValueError('Nested sensitivity needs at least three training players')
    folds = grouped_folds(train)
    paths, coefficients, path_predictions, assignments = [], [], [], []
    nested_metrics, nested_predictions = [], []

    def record(rows, splits, scope):
        for fold, (fit, valid) in enumerate(splits):
            for role, indices in [('fit', fit), ('validation', valid)]:
                for i in indices:
                    assignments.append({'scope': scope, 'fold': fold, 'role': role,
                                        'player_id': int(rows.iloc[i].player_id), 'season': int(rows.iloc[i].season)})

    record(train, folds, 'outer_and_final_tuning')
    for model, predictors in CONFIGURATIONS.items():
        metrics, beta, predictions = alpha_path(train, predictors, folds, grid, model=model, scope='outer_fixed_alpha')
        paths.append(metrics)
        coefficients.append(beta)
        path_predictions.append(predictions)
    for outer, (fit, valid) in enumerate(folds):
        fitting, validation = train.iloc[fit], train.iloc[valid]
        inner = grouped_folds(fitting)
        record(fitting, inner, f'outer_{outer}_inner')
        mean_pred = np.repeat(float(fitting.mlb_woba.mean()), len(validation))
        baseline = {'model': 'training_average', 'procedure': 'baseline', 'fold': outer, 'alpha': None,
                    'boundary': 'not_applicable', 'n_fit': len(fitting), 'n_validation': len(validation),
                    **regression_metrics(validation.mlb_woba, mean_pred)}
        baseline['validation_prediction_sd'] = 0.
        nested_metrics.append(baseline)
        p = validation[['player_id', 'season', 'mlb_woba']].rename(columns={'mlb_woba': 'y_true'}).copy()
        nested_predictions.append(p.assign(model='training_average', procedure='baseline', fold=outer, alpha=np.nan, y_pred=mean_pred))
        for model, predictors in CONFIGURATIONS.items():
            scores, beta, _ = alpha_path(fitting, predictors, inner, grid, model=model,
                                         scope=f'outer_{outer}_inner', save_predictions=False)
            paths.append(scores)
            coefficients.append(beta)
            for procedure, candidates in [('wide_grid', grid), ('original_grid', RIDGE_ALPHAS)]:
                alpha = choose_alpha(scores, candidates)
                pipeline = fit_at_alpha(fitting, predictors, alpha)
                stats, pred = fit_diagnostics(pipeline, fitting, validation, predictors)
                nested_metrics.append({'model': model, 'procedure': procedure, 'fold': outer,
                                       'alpha': alpha, 'boundary': boundary(alpha, candidates), **stats,
                                       **regression_metrics(validation.mlb_woba, pred)})
                nested_predictions.append(p.assign(model=model, procedure=procedure, fold=outer, alpha=alpha, y_pred=pred))
    paths = pd.concat(paths, ignore_index=True)
    coefficients = pd.concat(coefficients, ignore_index=True)
    path_predictions = pd.concat(path_predictions, ignore_index=True)
    nested_predictions = pd.concat(nested_predictions, ignore_index=True)
    nested_metrics = pd.DataFrame(nested_metrics)
    curves = curve_summary(paths.loc[paths.scope.eq('outer_fixed_alpha')], path_predictions)
    summaries = []
    for (model, procedure), p in nested_predictions.groupby(['model', 'procedure']):
        f = nested_metrics.loc[nested_metrics.model.eq(model) & nested_metrics.procedure.eq(procedure)]
        summaries.append({'model': model, 'procedure': procedure, 'n': len(p),
                          **regression_metrics(p.y_true, p.y_pred), 'prediction_spread': spread(p.y_pred),
                          'mean_fold_mae': float(f.mae.mean()), 'std_fold_mae': float(f.mae.std()),
                          'mean_fold_rmse': float(f.rmse.mean()), 'std_fold_rmse': float(f.rmse.std()),
                          'alpha_by_outer_fold': [None if pd.isna(v) else float(v) for v in f.alpha],
                          'boundary_counts': f.boundary.value_counts().to_dict()})
    final_choices, full_fits = {}, []
    for model, predictors in CONFIGURATIONS.items():
        scores = paths.loc[paths.model.eq(model) & paths.scope.eq('outer_fixed_alpha')]
        final_choices[model] = {}
        for procedure, candidates in [('wide_grid', grid), ('original_grid', RIDGE_ALPHAS)]:
            alpha = choose_alpha(scores, candidates)
            final_choices[model][procedure] = {'alpha': alpha, 'boundary': boundary(alpha, candidates)}
        # Full-training fits are diagnostics only; never evaluate test features or outcomes.
        for alpha in grid:
            pipeline = fit_at_alpha(train, predictors, alpha)
            pred = pipeline.predict(select_ablation_features(train, predictors))
            full_fits.append({'model': model, 'alpha': alpha, 'coefficient_l2': float(np.linalg.norm(pipeline['ridge'].coef_)),
                              'prediction_sd': float(np.std(pred)), 'prediction_variance': float(np.var(pred)),
                              **{f'train_{k}': v for k, v in regression_metrics(train.mlb_woba, pred).items()}})
    deltas = paired_changes(nested_predictions)
    summary = {
        'exploratory': True, 'target': 'Original provisional mlb_woba; unchanged', 'test_evaluated': False,
        'n_training_rows': len(train), 'n_training_players': train.player_id.nunique(),
        'observed_training_spread': spread(train.mlb_woba),
        'settings': {'wide_alphas': list(grid), 'original_alphas': list(RIDGE_ALPHAS), 'selection': 'Mean inner fold MAE; ascending alpha tie-break',
                     'folds': 'Deterministic GroupKFold, player_id, five outer and five inner folds',
                     'preprocessing': 'Fit-only median imputation; drop entirely missing columns; StandardScaler; Ridge SVD, intercept',
                     'configurations': CONFIGURATIONS},
        'nested_results': summaries, 'final_training_selection': final_choices,
        'paired_fold_differences': [
            {'model': model, 'comparator': comparator,
             **{metric: {'mean_delta': float(g[f'delta_{metric}_wide_minus_other'].mean()),
                         'std_delta': float(g[f'delta_{metric}_wide_minus_other'].std()),
                         'improved_folds': int(g[f'delta_{metric}_wide_minus_other'].lt(0).sum())} for metric in ['mae', 'rmse']}}
            for (model, comparator), g in deltas.groupby(['model', 'comparator'])],
        'caveats': ['Repeated exploratory use of the same 62 training players; no new independent validation.',
                    'Fixed-alpha curves and final selections reuse folds; nested results assess the selection procedure.',
                    'Outer folds share fitting players; fold variation is descriptive, not independent replications.',
                    'MAE tuning and squared-error Ridge fitting use different objectives; no causal signal claim.'],
    }
    return summary, {'alpha_fold_metrics': paths, 'coefficients': coefficients, 'fixed_alpha_predictions': path_predictions,
                     'alpha_summary': curves, 'nested_fold_metrics': nested_metrics, 'nested_predictions': nested_predictions,
                     'paired_fold_differences': deltas, 'fold_assignments': pd.DataFrame(assignments),
                     'full_training_path': pd.DataFrame(full_fits)}
