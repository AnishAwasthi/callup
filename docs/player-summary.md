# Player summaries (issue #10)

A local Hugging Face language model turns one player-season's statistics and saved model prediction into three short sections: **Strengths**, **Concerns** and **MLB outlook**. The language model only describes the supplied facts. The prediction itself comes from #4's saved run (`scripts/train_models.py`).

Reports are generated before the demo and saved in ignored `data/processed/player_reports/`. The app only loads them: no model runs while someone is browsing, and there are no paid API calls.

## Setup

```bash
pip install -r requirements-lock.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu   # or the CUDA build from pytorch.org
pip install -r requirements-llm.txt
hf download Qwen/Qwen2.5-1.5B-Instruct            # about 3 GB, cached outside the project
```

Default model: `Qwen/Qwen2.5-1.5B-Instruct` (Apache-2.0). It runs on a laptop CPU, or in fp16 on a 4 GB GPU. Pin the commit you used with `--llm-revision <sha>`; the model card lists commits under "Files and versions". Fallback: `HuggingFaceTB/SmolLM2-1.7B-Instruct` (Apache-2.0).

## Generate

```bash
python scripts/train_models.py                       # #4's saved predictions + metrics
python scripts/generate_player_reports.py --player-id <id> --season 2024 --llm-revision <sha>
python scripts/generate_player_reports.py --llm-revision <sha>          # every row with a saved prediction
python scripts/generate_player_reports.py --all --llm-revision <sha>    # all 926 player-seasons (hours on CPU)
python scripts/generate_player_reports.py --player-id <id> --season 2024 --print-prompt   # no model needed
```

Reruns skip reports whose inputs are unchanged; `--force` regenerates them anyway.

Each report `{player_id}_{season}.json` records:
- the exact facts supplied and the prompt messages
- the model id and resolved revision, plus the generation settings and library versions
- the check results and a fingerprint

`manifest.json` records the run.

**Generation settings:**
- greedy decoding (`do_sample=False`)
- `max_new_tokens=350`
- `repetition_penalty=1.05`
- seed 0
- fp16 on CUDA, fp32 on CPU

The prompt is in `callup/player_summary.py` (`SYSTEM_PROMPT`, `PROMPT_VERSION`).

## Factual checks

A report is shown only when all of these hold:

- **Exact headings.** All three headings are present, in order.
- **No new numbers.** Every number appears in the supplied facts; rounding a supplied number to fewer decimals is allowed.
- **No unsupported topics.** No injuries or health, mechanics or swing, scouting, defense or speed, promotion reasons, or certainty language.
- **Comparisons only when supplied.** No above/below-average or peer language unless a percentile comparison was supplied.
- **The outlook is accurate.** It states the saved prediction and describes it correctly relative to the training-average baseline.
- **Short sections.** Each section is 90 words or fewer.

When a player-season has no saved prediction (all 2023 rows and unlabeled 2024 rows), the model is not asked for an outlook. A fixed "No saved model prediction is available" sentence is shown instead.

The app rebuilds the facts from the current files and shows "Summary unavailable" in these cases:
- the report is missing
- any statistic, the prediction, the data or model version, the prompt or the language-model revision has changed (stale)
- the report failed the checks
- the file belongs to a different player-season

The fixed limitations box is shown under every summary.

## Preview and app

Use `python scripts/preview_report.py --player-id <id> --season <season>` to print the facts beside the report.

In the app (#7), after the statistics table:

```python
from callup.player_summary import facts_for_player, file_version, load_prediction_tables, load_report
from callup.summary_panel import render_summary

predictions, metrics = load_prediction_tables(PREDICTIONS, METRICS)
facts = facts_for_player(frame, player_id, season, predictions=predictions, metrics=metrics,
                         data_version=file_version(DATA_PATH))
render_summary(st, load_report(REPORT_DIR, player_id, season, facts))
```

## Placeholders to replace when other issues land

| Placeholder (`TODO` in code) | Replace with |
|---|---|
| `DEFAULT_SUMMARY_STATS` | #7's display-settings file |
| `load_prediction_tables` / `find_prediction` | #9's table-loading interface |
| `RATE_DEFINITIONS`, `same_season_comparisons` (percentiles among same-season study hitters) | Approved #1 rates in #8's `player_features.csv` |
| `--input` default `hitter_seasons.csv` | `data/processed/player_features.csv` (#8) |

Changing any of these changes the facts, so existing reports are marked stale until they are regenerated.

## Review checklist

Before the demo, review at least five players across both seasons, including ones with and without a prediction:

- Every number matches the facts table.
- Comparisons follow the stated percentile direction.
- There are no claims beyond the facts.
- The limitations are visible.
- Switching players never shows another player's report.

Do not commit real reports or model weights.
