"""Bounded, training-only feature, learning-curve and grouped-split Ridge study."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.impute import SimpleImputer
from sklearn.model_selection import GroupKFold

from callup.contract import FEATURE_INPUTS
from callup.modeling import RIDGE_ALPHAS, labeled_partitions, regression_metrics, ridge_pipeline
from callup.ridge_ablation import BATTED_PREDICTORS

RATES = ['aaa_bb_rate', 'aaa_k_rate', 'aaa_hr_rate', 'aaa_ba']
RATE_PREDICTORS = ['aaa_pa', *RATES]
EV = BATTED_PREDICTORS[:4]
LA = BATTED_PREDICTORS[4:]
CONFIGURATIONS = {
    'counts': list(FEATURE_INPUTS), 'rates': RATE_PREDICTORS,
    'rates_batted': RATE_PREDICTORS + BATTED_PREDICTORS,
    'counts_batted': list(FEATURE_INPUTS) + BATTED_PREDICTORS,
    'counts_ev': list(FEATURE_INPUTS) + EV, 'counts_la': list(FEATURE_INPUTS) + LA,
    **{f'counts_{p}': list(FEATURE_INPUTS) + [p] for p in BATTED_PREDICTORS},
}
PRIMARY = ['counts', 'rates', 'rates_batted']
SPLIT_SEEDS = (-1, 0, 1, 2, 3, 4, 5)  # -1 is the original unshuffled GroupKFold.
LEARNING_SIZES = (10, 20, 30, 40)
SUBSET_REPETITIONS = 5


def safe_divide(numerator, denominator):
    n, d = pd.to_numeric(numerator, errors='raise'), pd.to_numeric(denominator, errors='raise')
    if np.isinf(n.to_numpy(dtype=float)).any() or np.isinf(d.to_numpy(dtype=float)).any() or d.lt(0).any():
        raise ValueError('Invalid numerator or denominator')
    return n.div(d.where(d.gt(0)))


def engineer_rates(frame):
    if set(RATES) & set(frame.columns):
        raise ValueError('Rate columns already exist')
    result = frame.copy()
    for output, numerator, denominator in [
        ('aaa_bb_rate', 'aaa_bb', 'aaa_pa'), ('aaa_k_rate', 'aaa_k', 'aaa_pa'),
        ('aaa_hr_rate', 'aaa_hr', 'aaa_pa'), ('aaa_ba', 'aaa_hits', 'aaa_ab'),
    ]:
        result[output] = safe_divide(frame[numerator], frame[denominator])
    pd.testing.assert_frame_equal(result[frame.columns], frame)
    return result


def select_features(rows, predictors):
    allowed = set(FEATURE_INPUTS + RATES + BATTED_PREDICTORS)
    if not predictors or len(set(predictors)) != len(predictors) or set(predictors) - allowed:
        raise ValueError('Predictors outside study allowlist')
    X = rows[list(predictors)]
    if not all(pd.api.types.is_numeric_dtype(d) for d in X.dtypes) or np.isinf(X.to_numpy(dtype=float)).any():
        raise ValueError('Non-numeric or infinite predictor')
    return X


def grouped_folds(rows, seed=-1):
    n = min(5, rows.player_id.nunique())
    if n < 2:
        raise ValueError('At least two fitting players required')
    return list(GroupKFold(n_splits=n, shuffle=seed != -1,
                          random_state=None if seed == -1 else seed).split(rows, groups=rows.player_id))


def tune(fitting, predictors, folds, alphas=RIDGE_ALPHAS):
    """Cache alpha-independent fold preprocessing; equivalent to fresh Pipeline fits per alpha."""
    candidates = np.asarray(alphas, dtype=float)
    if len(candidates) == 0 or np.any(~np.isfinite(candidates)) or np.any(candidates <= 0) or np.any(np.diff(candidates) <= 0):
        raise ValueError('Alpha grid must be positive and increasing')
    scores = []
    for fold, (fit, valid) in enumerate(folds):
        a, b = fitting.iloc[fit], fitting.iloc[valid]
        if set(a.player_id) & set(b.player_id):
            raise ValueError('Player overlap within tuning fold')
        pipe = ridge_pipeline()
        pipe.set_params(imputer=SimpleImputer(strategy='median', keep_empty_features=False))
        preprocessing = pipe[:-1]
        X_fit = preprocessing.fit_transform(select_features(a, predictors), a.mlb_woba)
        X_valid = preprocessing.transform(select_features(b, predictors))
        for alpha in candidates:
            ridge = clone(pipe['ridge']).set_params(alpha=float(alpha))
            ridge.fit(X_fit, a.mlb_woba)
            m = regression_metrics(b.mlb_woba, ridge.predict(X_valid))
            scores.append({'inner_fold': fold, 'alpha': float(alpha), 'mae': m['mae'], 'rmse': m['rmse']})
    scores = pd.DataFrame(scores)
    means = scores.groupby('alpha', sort=True).mae.mean()
    alpha = float(means.idxmin())
    final = ridge_pipeline()
    final.set_params(imputer=SimpleImputer(strategy='median', keep_empty_features=False), ridge__alpha=alpha)
    final.fit(select_features(fitting, predictors), fitting.mlb_woba)
    return final, alpha, scores


def subset_indices(fitting, size, seed):
    players = np.array(sorted(fitting.player_id.unique()))
    if not 2 <= size <= len(players):
        raise ValueError('Invalid player subset size')
    chosen = np.random.default_rng(seed).permutation(players)[:size]
    return np.flatnonzero(fitting.player_id.isin(chosen))


def study(frame, *, seeds=SPLIT_SEEDS, sizes=LEARNING_SIZES, subset_repetitions=SUBSET_REPETITIONS,
          configurations=None, progress=None):
    configurations = CONFIGURATIONS if configurations is None else configurations
    if not set(PRIMARY) <= set(configurations) or len(set(seeds)) != len(seeds) or -1 not in seeds:
        raise ValueError('Primary configurations and original split required')
    if subset_repetitions < 1 or any(s < 2 for s in sizes) or len(set(sizes)) != len(sizes):
        raise ValueError('Invalid learning-curve design')
    train, _ = labeled_partitions(frame)
    train = train.reset_index(drop=True)
    if train.player_id.nunique() < 4:
        raise ValueError('Nested study requires at least four training players')
    rows, predictions, assignments, inner_scores = [], [], [], []
    learning_rows, learning_predictions, subsets = [], [], []

    def record_assignments(fitting, validation, inner, identity):
        if set(fitting.player_id) & set(validation.player_id):
            raise ValueError('Outer validation overlap')
        for role, selected in [('fit', fitting), ('validation', validation)]:
            for p in selected.itertuples():
                assignments.append({**identity, 'inner_fold': -1, 'role': role,
                                    'player_id': int(p.player_id), 'season': int(p.season)})
        for fold, (fit, valid) in enumerate(inner):
            for role, indices in [('inner_fit', fit), ('inner_validation', valid)]:
                for p in fitting.iloc[indices].itertuples():
                    assignments.append({**identity, 'inner_fold': fold, 'role': role,
                                        'player_id': int(p.player_id), 'season': int(p.season)})

    def evaluate(fitting, validation, inner, configs, identity):
        result, preds = [], []
        for model, predictors in {'training_average': [], **configs}.items():
            if model == 'training_average':
                value = float(fitting.mlb_woba.mean())
                fit_pred, val_pred = np.repeat(value, len(fitting)), np.repeat(value, len(validation))
                alpha = None
            else:
                pipeline, alpha, scores = tune(fitting, predictors, inner)
                inner_scores.extend({**identity, 'model': model, **record} for record in scores.to_dict('records'))
                fit_pred = pipeline.predict(select_features(fitting, predictors))
                val_pred = pipeline.predict(select_features(validation, predictors))
            fit_m = regression_metrics(fitting.mlb_woba, fit_pred)
            val_m = regression_metrics(validation.mlb_woba, val_pred)
            result.append({**identity, 'model': model, 'alpha': alpha,
                           'n_fit': len(fitting), 'n_fit_players': fitting.player_id.nunique(),
                           'n_validation': len(validation), 'n_validation_players': validation.player_id.nunique(),
                           **{f'train_{m}': fit_m[m] for m in ['mae', 'rmse']},
                           **{f'validation_{m}': val_m[m] for m in ['mae', 'rmse']},
                           'prediction_sd': float(np.std(val_pred))})
            p = validation[['player_id', 'season', 'mlb_woba']].rename(columns={'mlb_woba': 'y_true'}).copy()
            preds.append(p.assign(**identity, model=model, y_pred=val_pred))
        return result, pd.concat(preds, ignore_index=True)

    # A/C/D: configurations always share every outer/inner assignment within a repetition.
    for seed in seeds:
        for outer, (fit, valid) in enumerate(grouped_folds(train, seed)):
            fitting, validation = train.iloc[fit], train.iloc[valid]
            inner = grouped_folds(fitting, -1 if seed == -1 else 10000 + seed * 100 + outer)
            identity = {'experiment': 'validation', 'split_seed': seed, 'outer_fold': outer,
                        'size_label': 'all', 'subset_repeat': 0}
            record_assignments(fitting, validation, inner, identity)
            result, preds = evaluate(fitting, validation, inner, configurations, identity)
            rows.extend(result)
            predictions.append(preds)
            if seed == -1:
                keep = ['training_average', *PRIMARY]
                learning_rows.extend({**r, 'experiment': 'learning'} for r in result if r['model'] in keep)
                learning_predictions.append(preds.loc[preds.model.isin(keep)].assign(experiment='learning'))
        if progress:
            progress(f'Completed grouped split seed {seed}')

    # B: nested prefixes of the same random player permutation keep size comparisons paired.
    for outer, (fit, valid) in enumerate(grouped_folds(train, -1)):
        pool, validation = train.iloc[fit], train.iloc[valid]
        for repeat in range(subset_repetitions):
            sample_seed = 20000 + 100 * outer + repeat
            for size in sizes:
                if size > pool.player_id.nunique():
                    raise ValueError('Learning size exceeds available outer-fitting players')
                fitting = pool.iloc[subset_indices(pool, size, sample_seed)]
                identity = {'experiment': 'learning', 'split_seed': -1, 'outer_fold': outer,
                            'size_label': str(size), 'subset_repeat': repeat}
                for p in fitting.itertuples():
                    subsets.append({**identity, 'subset_seed': sample_seed, 'player_id': int(p.player_id), 'season': int(p.season)})
                inner = grouped_folds(fitting, -1)
                record_assignments(fitting, validation, inner, identity)
                result, preds = evaluate(fitting, validation, inner, {p: configurations[p] for p in PRIMARY}, identity)
                learning_rows.extend(result)
                learning_predictions.append(preds)
        if progress:
            progress(f'Completed learning subsets for outer fold {outer + 1}')
    metrics = pd.DataFrame(rows)
    predictions = pd.concat(predictions, ignore_index=True)
    learning = pd.DataFrame(learning_rows)
    learning_predictions = pd.concat(learning_predictions, ignore_index=True)
    repetition = repetition_metrics(metrics, predictions, ['split_seed'])
    learning_repetition = repetition_metrics(learning, learning_predictions, ['size_label', 'subset_repeat'])
    stability = stability_summary(repetition)
    contributions = contribution_summary(repetition)
    learning_summary = summarize_learning(learning_repetition)
    summary = {
        'exploratory': True, 'holdout_evaluated': False,
        'n_training_rows': len(train), 'n_training_players': train.player_id.nunique(),
        'design': {'configurations': configurations, 'alpha_grid': list(RIDGE_ALPHAS), 'split_seeds': list(seeds),
                   'learning_sizes': list(sizes) + ['all'], 'subset_repetitions_small_sizes': subset_repetitions,
                   'tuning': 'Nested five-fold player GroupKFold; mean inner MAE; ascending alpha tie-break',
                   'missingness': 'Fit-only median imputation; drop entirely empty fit columns; no target imputation',
                   'rate_denominators': 'BB/PA, K/PA, HR/PA, H/AB; zero denominator -> missing'},
        'original_split_results': json_records(repetition.loc[repetition.split_seed.eq(-1)]),
        'random_split_stability': json_records(stability), 'feature_contributions': json_records(contributions),
        'learning_curves': json_records(learning_summary),
        'limits': ['Only 62 players in one training outcome year; provisional outcomes unchanged.',
                   'Repeated splits reuse the same players; split variation is not future-season uncertainty.',
                   'Many predeclared comparisons are exploratory; no winner is independently confirmed.',
                   'Learning-curve variation conditions on fixed validation folds; no numerical extrapolation beyond observed sizes.'],
    }
    return summary, {'validation_fold_metrics': metrics, 'validation_predictions': predictions,
                     'repetition_metrics': repetition, 'stability_summary': stability, 'feature_contributions': contributions,
                     'learning_fold_metrics': learning, 'learning_predictions': learning_predictions,
                     'learning_repetition_metrics': learning_repetition, 'learning_summary': learning_summary,
                     'fold_assignments': pd.DataFrame(assignments), 'subset_assignments': pd.DataFrame(subsets),
                     'inner_alpha_scores': pd.DataFrame(inner_scores)}


def json_records(frame):
    import json
    return json.loads(frame.to_json(orient='records', double_precision=15))


def repetition_metrics(folds, predictions, group_columns):
    records = []
    for key, p in predictions.groupby([*group_columns, 'model'], sort=False):
        identity = dict(zip([*group_columns, 'model'], key, strict=True))
        selected = folds
        for column, value in identity.items():
            selected = selected.loc[selected[column].eq(value)]
        if p.duplicated(['player_id', 'season']).any():
            raise ValueError('Repeated player-season within an OOF repetition')
        records.append({**identity, 'n_validation': len(p), 'n_fit_min': int(selected.n_fit.min()),
                        'n_fit_max': int(selected.n_fit.max()),
                        **{f'validation_{m}': v for m, v in regression_metrics(p.y_true, p.y_pred).items() if m in ['mae', 'rmse']},
                        **{f'train_{m}': float(selected[f'train_{m}'].mean()) for m in ['mae', 'rmse']},
                        'prediction_sd': float(p.y_pred.std(ddof=0))})
    result = pd.DataFrame(records)
    baseline = result.loc[result.model.eq('training_average'), [*group_columns, 'validation_mae', 'validation_rmse']]
    result = result.merge(baseline, on=group_columns, suffixes=('', '_baseline'), validate='many_to_one')
    for metric in ['mae', 'rmse']:
        result[f'delta_{metric}_vs_baseline'] = result[f'validation_{metric}'] - result[f'validation_{metric}_baseline']
    result['mae_rank'] = result.groupby(group_columns).validation_mae.rank(method='min')
    result['rmse_rank'] = result.groupby(group_columns).validation_rmse.rank(method='min')
    return result


def stability_summary(repetition):
    random = repetition.loc[repetition.split_seed.ne(-1)]
    records = []
    for model, group in random.groupby('model', sort=False):
        row = {'model': model, 'n_split_repetitions': len(group)}
        for column in ['validation_mae', 'validation_rmse', 'delta_mae_vs_baseline', 'delta_rmse_vs_baseline', 'mae_rank', 'rmse_rank']:
            row.update({f'mean_{column}': float(group[column].mean()), f'std_{column}': float(group[column].std()),
                        f'min_{column}': float(group[column].min()), f'max_{column}': float(group[column].max())})
        row['mae_improved_seeds'] = int(group.delta_mae_vs_baseline.lt(0).sum())
        row['rmse_improved_seeds'] = int(group.delta_rmse_vs_baseline.lt(0).sum())
        records.append(row)
    return pd.DataFrame(records)


def contribution_summary(repetition):
    random = repetition.loc[repetition.split_seed.ne(-1)]
    comparisons = [(model, 'counts') for model in CONFIGURATIONS if model.startswith('counts_')]
    comparisons += [('rates', 'counts'), ('rates_batted', 'rates'), ('counts_batted', 'counts_ev'), ('counts_batted', 'counts_la')]
    records = []
    for added, reference in comparisons:
        a, b = random.loc[random.model.eq(added)], random.loc[random.model.eq(reference)]
        if a.empty or b.empty:
            continue
        paired = a.merge(b, on='split_seed', suffixes=('_added', '_reference'), validate='one_to_one')
        row = {'model': added, 'reference': reference, 'n_seeds': len(paired)}
        for metric in ['mae', 'rmse']:
            delta = paired[f'validation_{metric}_added'] - paired[f'validation_{metric}_reference']
            row.update({f'mean_delta_{metric}': float(delta.mean()), f'std_delta_{metric}': float(delta.std()),
                        f'min_delta_{metric}': float(delta.min()), f'max_delta_{metric}': float(delta.max()),
                        f'improved_{metric}_seeds': int(delta.lt(0).sum())})
        records.append(row)
    return pd.DataFrame(records)


def summarize_learning(repetition):
    records = []
    for (size, model), group in repetition.groupby(['size_label', 'model'], sort=False):
        row = {'size_label': size, 'model': model, 'n_subset_draws': len(group),
               'n_fit_min': int(group.n_fit_min.min()), 'n_fit_max': int(group.n_fit_max.max()),
               'n_validation_per_draw': int(group.n_validation.iloc[0])}
        for column in ['train_mae', 'train_rmse', 'validation_mae', 'validation_rmse', 'delta_mae_vs_baseline', 'delta_rmse_vs_baseline']:
            row[f'mean_{column}'] = float(group[column].mean())
            row[f'std_{column}'] = float(group[column].std())
        records.append(row)
    return pd.DataFrame(records)
