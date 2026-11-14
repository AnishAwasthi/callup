"""Readable player summaries: fact sheets, prompts, factual checks and report lookup.

The language model only *describes* supplied facts. The statistical prediction comes from
#4's saved run; nothing here creates or changes a prediction. This module has no ML
dependencies so CI can test it; the Hugging Face backend lives in ``callup.hf_generator``.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

PROMPT_VERSION = "v1"
OUTLOOK = "MLB outlook"
HEADINGS_WITH_PREDICTION = ("Strengths", "Concerns", OUTLOOK)
HEADINGS_WITHOUT_PREDICTION = ("Strengths", "Concerns")
NO_PREDICTION_OUTLOOK = (
    "No saved model prediction is available for this player-season, so no MLB outlook is given."
)
MAX_SECTION_WORDS = 90

# TODO(#7): replace with the approved stats/labels from #7's display-settings file.
DEFAULT_SUMMARY_STATS = [
    {"column": "aaa_pa", "label": "Triple-A plate appearances"},
    {"column": "aaa_ab", "label": "Triple-A at-bats"},
    {"column": "aaa_hits", "label": "Triple-A hits"},
    {"column": "aaa_bb", "label": "Triple-A walks"},
    {"column": "aaa_k", "label": "Triple-A strikeouts"},
    {"column": "aaa_hr", "label": "Triple-A home runs"},
]

# TODO(#1/#8): use approved #1 rate features from player_features.csv once merged.
# (key, label, numerator, denominator, format, meaning of a higher value)
RATE_DEFINITIONS = [
    ("avg", "Triple-A batting average (hits / at-bats)", "aaa_hits", "aaa_ab", "avg",
     "more hits per at-bat"),
    ("bb_rate", "Triple-A walk rate (walks / plate appearances)", "aaa_bb", "aaa_pa", "pct",
     "walks more often"),
    ("k_rate", "Triple-A strikeout rate (strikeouts / plate appearances)", "aaa_k", "aaa_pa", "pct",
     "strikes out more often, which is generally unfavorable"),
    ("hr_rate", "Triple-A home-run rate (home runs / plate appearances)", "aaa_hr", "aaa_pa", "pct",
     "hits home runs more often"),
]

LIMITATIONS = [
    "MLB wOBA outcomes are provisional and independent validation is still pending, so model "
    "results are preliminary.",
    "The model was evaluated only on players with at least 75 MLB plate appearances in the "
    "following season.",
    "The prediction is next-season MLB wOBA, not a probability of being called up and not a "
    "projected batting line.",
]

SYSTEM_PROMPT = """You write short, factual baseball summaries for a research project.
Use ONLY the facts supplied by the user. Follow every rule:
1. Write exactly these headings, each on its own line followed by 1-3 plain sentences: {headings}.
2. Every number you write must appear in the facts. Do not calculate new numbers.
3. Do not mention injuries, health, swing or mechanics, scouting opinions, defense, speed,
   attitude, coaching, or reasons for a promotion or demotion. None of these are in the facts.
4. Only say a player is above, below, better or worse than other hitters when a percentile
   comparison is supplied, and describe it in the stated direction.
5. {outlook_rule}
6. Do not add a title, bullet points, or any other heading."""

OUTLOOK_RULE = (
    "Under MLB outlook, describe the predicted next-season MLB wOBA as the statistical model's "
    "estimate, compare it with the training-average baseline only as supplied, and say the "
    "result is preliminary."
)
NO_OUTLOOK_RULE = "There is no model prediction; do not write an MLB outlook or forecast."

BANNED_PATTERNS = {
    "injury or health": r"\binjur|\bhealth|\bhurt\b|\binjured\b|\brehab",
    "mechanics or swing": r"\bmechanic|\bswing|\bstance\b|\bbat speed|\bbat path",
    "scouting opinion": r"\bscout|\btools?\b|\bmakeup\b|\bwork ethic|\battitude|\bcoach",
    "defense or speed": r"\bdefen[cs]|\bglove|\barm strength|\bspeed\b|\bstolen bases?\b|\bsprint",
    "promotion reason": r"\bpromot|\bdemot|\bcalled up because|\bsent down",
    "certainty": r"\bguarantee|\bdefinitely\b|\bcertain to\b|\bwill surely",
}
PEER_COMPARISON = re.compile(
    r"\b(above|below)[- ](average|the league|league|his peers|most|other)|\bleague[- ]average"
    r"|\bpercentile|\bpeers\b|\bbetter than\b|\bworse than\b|\bamong the (best|worst|top)"
    r"|\belite\b|\b(top|bottom) \d", re.IGNORECASE,
)
NUMBER = re.compile(r"(?<![\w.])(?:\d+(?:\.\d+)?|\.\d+)")


# --------------------------------------------------------------------------- formatting

def format_woba(value: float) -> str:
    return f"{value:.3f}".removeprefix("0")


def format_rate(value: float, kind: str) -> str:
    return format_woba(value) if kind == "avg" else f"{100 * value:.1f}%"


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def file_version(path) -> str:
    """Same identifier pattern as scripts/train_models.py."""
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --------------------------------------------------------------------------- facts

def _rate(row, numerator, denominator):
    numerator, denominator = row.get(numerator), row.get(denominator)
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return None
    return float(numerator) / float(denominator)


def same_season_comparisons(frame: pd.DataFrame, row) -> list[dict]:
    """Percentile of each rate among same-season study hitters (deterministic, no LLM).

    TODO(#1/#8): switch to the approved comparison features once #8's table is merged.
    """
    peers = frame.loc[frame.season.eq(row["season"])]
    comparisons = []
    for key, label, numerator, denominator, _, higher in RATE_DEFINITIONS:
        value = _rate(row, numerator, denominator)
        values = (peers[numerator] / peers[denominator].where(peers[denominator] > 0)).dropna()
        if value is None or len(values) < 2:
            continue
        below = int((values < value).sum())
        ties = int((values == value).sum())
        percentile = round(100 * (below + 0.5 * ties) / len(values))
        percentile = min(max(percentile, 1), 99)
        comparisons.append({
            "key": key,
            "label": f"{label}, compared with {len(values)} study hitters in {row['season']}",
            "value": f"{ordinal(percentile)} percentile (a higher percentile means {higher})",
        })
    return comparisons


@dataclass(frozen=True)
class SavedPrediction:
    model: str
    split: str
    outcome_year: int
    y_pred: float
    baseline: float | None
    y_true: float | None
    data_version: str
    code_version: str
    code_dirty: bool


def load_prediction_tables(predictions_path, metrics_path):
    """Load #4's saved run. TODO(#9): replace with #9's table-loading interface."""
    predictions_path, metrics_path = Path(predictions_path), Path(metrics_path)
    if not predictions_path.exists() or not metrics_path.exists():
        return None, None
    return pd.read_csv(predictions_path), json.loads(metrics_path.read_text())


def find_prediction(predictions, metrics, player_id, season, model="ridge"):
    """Return the saved prediction for one player-season, or None when unavailable.

    Raises when the files disagree (duplicate rows, or metrics from a different run), so a
    report is never built from mixed model runs.
    """
    if predictions is None or metrics is None:
        return None
    key = predictions.player_id.eq(player_id) & predictions.season.eq(season)
    rows = predictions.loc[key & predictions.model.eq(model)]
    if rows.empty:
        return None
    if len(rows) > 1:
        raise ValueError(f"Multiple {model} predictions for player {player_id}, season {season}")
    row = rows.iloc[0]
    run = metrics.get("models", {}).get(model)
    if run is None or (run.get("data_version"), run.get("code_version")) != (
            row.data_version, row.code_version):
        raise ValueError("predictions.csv and model_metrics.json come from different runs")
    baseline_rows = predictions.loc[key & predictions.model.eq("training_average")]
    baseline = float(baseline_rows.y_pred.iloc[0]) if len(baseline_rows) == 1 else None
    return SavedPrediction(
        model=model, split=str(row.split), outcome_year=int(row.outcome_year),
        y_pred=float(row.y_pred), baseline=baseline,
        y_true=None if pd.isna(row.y_true) else float(row.y_true),
        data_version=str(row.data_version), code_version=str(row.code_version),
        code_dirty=bool(row.code_dirty),
    )


def build_facts(row, *, prediction: SavedPrediction | None, comparisons: list[dict],
                data_version: str, display_settings=DEFAULT_SUMMARY_STATS) -> dict:
    """Canonical fact sheet. Every value is the exact string shown to the language model."""
    statistics = []
    for setting in display_settings:
        value = row.get(setting["column"])
        statistics.append({"label": setting["label"],
                           "value": "unavailable" if pd.isna(value) else str(int(value))})
    rates = []
    for _, label, numerator, denominator, kind, _ in RATE_DEFINITIONS:
        value = _rate(row, numerator, denominator)
        rates.append({"label": label,
                      "value": "unavailable" if value is None else format_rate(value, kind)})
    facts = {
        "player": {"player_id": int(row["player_id"]), "name": str(row["name"]),
                   "season": int(row["season"]), "outcome_year": int(row["outcome_year"])},
        "statistics": statistics,
        "rates": rates,
        "comparisons": comparisons,
        "prediction": None,
        "limitations": list(LIMITATIONS),
        "versions": {"input_data_version": data_version},
    }
    if prediction is not None:
        facts["prediction"] = {
            "model": prediction.model,
            "predicted_next_season_mlb_woba": format_woba(prediction.y_pred),
            "training_average_baseline_woba": (None if prediction.baseline is None
                                               else format_woba(prediction.baseline)),
            "outcome_year": prediction.outcome_year,
            "split": prediction.split,
            "observed_provisional_mlb_woba": (None if prediction.y_true is None
                                              else format_woba(prediction.y_true)),
        }
        facts["versions"].update({
            "model": prediction.model,
            "prediction_data_version": prediction.data_version,
            "prediction_code_version": prediction.code_version,
            "prediction_code_dirty": prediction.code_dirty,
        })
    return facts


def facts_for_player(frame, player_id, season, *, predictions, metrics, data_version,
                     model="ridge", display_settings=DEFAULT_SUMMARY_STATS) -> dict:
    """Build facts by player ID and season (never by name). Shared by the script and the app."""
    rows = frame.loc[frame.player_id.eq(player_id) & frame.season.eq(season)]
    if len(rows) != 1:
        raise KeyError(f"Expected one row for player {player_id}, season {season}; got {len(rows)}")
    row = rows.iloc[0]
    return build_facts(
        row, prediction=find_prediction(predictions, metrics, player_id, season, model),
        comparisons=same_season_comparisons(frame, row), data_version=data_version,
        display_settings=display_settings,
    )


# --------------------------------------------------------------------------- prompt

def headings_for(facts) -> tuple[str, ...]:
    return HEADINGS_WITH_PREDICTION if facts["prediction"] else HEADINGS_WITHOUT_PREDICTION


def _fact_lines(facts) -> list[str]:
    player = facts["player"]
    lines = [f"Player: {player['name']}", f"Triple-A season: {player['season']}"]
    lines += [f"{item['label']}: {item['value']}" for item in facts["statistics"] + facts["rates"]]
    lines += [f"{item['label']}: {item['value']}" for item in facts["comparisons"]]
    if not facts["comparisons"]:
        lines.append("No comparisons with other hitters are supplied.")
    prediction = facts["prediction"]
    if prediction:
        year = prediction["outcome_year"]
        lines.append(f"Statistical model ({prediction['model']}) predicted {year} MLB wOBA: "
                     f"{prediction['predicted_next_season_mlb_woba']}")
        if prediction["training_average_baseline_woba"]:
            lines.append("Training-average baseline wOBA (the same value for every player): "
                         f"{prediction['training_average_baseline_woba']}")
        if prediction["observed_provisional_mlb_woba"]:
            lines.append(f"Observed {year} MLB wOBA, provisional and held out from training: "
                         f"{prediction['observed_provisional_mlb_woba']}")
    else:
        lines.append("No saved model prediction is available.")
    lines.append("wOBA is a batting statistic that weights each way of reaching base.")
    lines += [f"Limitation: {text}" for text in facts["limitations"]]
    return lines


def build_messages(facts) -> list[dict]:
    rule = OUTLOOK_RULE if facts["prediction"] else NO_OUTLOOK_RULE
    system = SYSTEM_PROMPT.format(headings=", ".join(headings_for(facts)), outlook_rule=rule)
    return [{"role": "system", "content": system},
            {"role": "user", "content": "Facts:\n" + "\n".join(_fact_lines(facts))}]


def prompt_sha() -> str:
    template = json.dumps([SYSTEM_PROMPT, OUTLOOK_RULE, NO_OUTLOOK_RULE, PROMPT_VERSION])
    return "sha256:" + hashlib.sha256(template.encode()).hexdigest()


def fingerprint(facts: dict, llm_config: dict) -> str:
    """Changes when any fact, version, prompt or generation setting changes."""
    payload = {"facts": facts, "llm": llm_config, "prompt_version": PROMPT_VERSION,
               "prompt_sha": prompt_sha()}
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# --------------------------------------------------------------------------- checking

def parse_sections(text: str, headings) -> dict[str, str]:
    """Split model output on the exact headings; raise ValueError if the shape is wrong."""
    names = "|".join(map(re.escape, HEADINGS_WITH_PREDICTION))
    # "Strengths", "## Strengths", "**Strengths:**" or "Strengths: text on the same line".
    pattern = re.compile(
        r"^[ \t]*(?:#+[ \t]*)?(?:\*\*)?[ \t]*(" + names + r")[ \t]*"
        r"(?:\*\*[ \t]*:?|:(?:[ \t]*\*\*)?|(?=\n|\Z))", re.IGNORECASE | re.MULTILINE)
    matches = list(pattern.finditer(text))
    found = [m.group(1).lower() for m in matches]
    if found != [h.lower() for h in headings]:
        raise ValueError(f"Expected headings {list(headings)}, found {found}")
    sections = {}
    for match, nxt, heading in zip(matches, [*matches[1:], None], headings, strict=True):
        body = text[match.end(): nxt.start() if nxt else len(text)].strip()
        if not body:
            raise ValueError(f"Empty section: {heading}")
        sections[heading] = " ".join(body.split())
    return sections


def _allowed_numbers(facts) -> list[str]:
    visible = {key: facts[key] for key in
               ("statistics", "rates", "comparisons", "prediction", "limitations")}
    visible["player"] = {k: v for k, v in facts["player"].items() if k != "player_id"}
    numbers = NUMBER.findall(json.dumps(visible))
    return sorted(set(numbers + ["1", "2", "3"]))  # small counting words are harmless


def _matches_fact(number: str, allowed: list[str]) -> bool:
    value = float(number)
    decimals = len(number.split(".")[1]) if "." in number else 0
    for fact in allowed:
        fact_value = float(fact)
        if math.isclose(value, fact_value) or math.isclose(value, round(fact_value, decimals)):
            return True  # exact, or the same fact written with fewer decimals
    return False


def check_report(sections: dict[str, str], facts: dict) -> list[str]:
    """Return reasons to reject the report; an empty list means it passed."""
    failures = []
    allowed = _allowed_numbers(facts)
    for heading, body in sections.items():
        words = len(body.split())
        if words > MAX_SECTION_WORDS:
            failures.append(f"{heading}: {words} words exceeds {MAX_SECTION_WORDS}")
        for number in NUMBER.findall(body):
            if not _matches_fact(number, allowed):
                failures.append(f"{heading}: number {number} is not in the supplied facts")
        for topic, pattern in BANNED_PATTERNS.items():
            if re.search(pattern, body, re.IGNORECASE):
                failures.append(f"{heading}: unsupported claim about {topic}")
        if not facts["comparisons"] and PEER_COMPARISON.search(body):
            failures.append(f"{heading}: comparison with other hitters, but none was supplied")
    prediction = facts["prediction"]
    if prediction and OUTLOOK in sections:
        outlook = sections[OUTLOOK]
        if prediction["predicted_next_season_mlb_woba"] not in re.sub(r"\b0\.(?=\d)", ".", outlook):
            failures.append("MLB outlook: does not state the saved prediction")
        failures += _baseline_direction(outlook, prediction)
    return failures


def _baseline_direction(outlook: str, prediction: dict) -> list[str]:
    baseline = prediction["training_average_baseline_woba"]
    if baseline is None:
        return []
    above = float(prediction["predicted_next_season_mlb_woba"]) > float(baseline)
    for sentence in re.split(r"(?<=[.!?])\s+", outlook):
        if "baseline" not in sentence.lower():
            continue
        says_above = re.search(r"\b(above|higher|exceeds|better)\b", sentence, re.IGNORECASE)
        says_below = re.search(r"\b(below|lower|under|worse)\b", sentence, re.IGNORECASE)
        if (says_above and not says_below and not above) or (says_below and not says_above
                                                             and above):
            return ["MLB outlook: states the wrong direction versus the baseline"]
    return []


def finalize_sections(sections: dict[str, str], facts: dict) -> dict[str, str]:
    """Add the fixed outlook text when no prediction exists (the LLM never writes one)."""
    if facts["prediction"] is None:
        return {**sections, OUTLOOK: NO_PREDICTION_OUTLOOK}
    return sections


# --------------------------------------------------------------------------- reports

def report_path(report_dir, player_id, season) -> Path:
    return Path(report_dir) / f"{int(player_id)}_{int(season)}.json"


def make_report(facts, raw_text, llm_config, generated_at, runtime=None) -> dict:
    """``llm_config`` decides staleness; ``runtime`` (device, library versions) is recorded."""
    headings = headings_for(facts)
    try:
        sections = parse_sections(raw_text, headings)
        failures = check_report(sections, facts)
    except ValueError as error:
        sections, failures = {}, [str(error)]
    return {
        "player_id": facts["player"]["player_id"],
        "season": facts["player"]["season"],
        "name": facts["player"]["name"],
        "status": "rejected" if failures else "ok",
        "check_failures": failures,
        "sections": finalize_sections(sections, facts) if not failures else sections,
        "raw_output": raw_text,
        "facts": facts,
        "fingerprint": fingerprint(facts, llm_config),
        "llm": llm_config,
        "llm_runtime": runtime or {},
        "prompt_version": PROMPT_VERSION,
        "prompt_sha": prompt_sha(),
        "messages": build_messages(facts),
        "generated_at": generated_at,
    }


@dataclass(frozen=True)
class ReportLookup:
    status: str  # ok | missing | stale | rejected | invalid
    report: dict | None = None
    reason: str = ""

    @property
    def available(self) -> bool:
        return self.status == "ok"


def load_report(report_dir, player_id, season, current_facts: dict) -> ReportLookup:
    """Load the report for exactly this player-season and check it is current and passed."""
    path = report_path(report_dir, player_id, season)
    if not path.exists():
        return ReportLookup("missing", reason="No report has been generated for this player-season.")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        identity = (int(report["player_id"]), int(report["season"]))
    except (OSError, ValueError, KeyError, TypeError) as error:
        return ReportLookup("invalid", reason=f"Report file could not be read: {error}")
    if identity != (int(player_id), int(season)):
        return ReportLookup("invalid", reason="Report belongs to a different player-season.")
    if report.get("fingerprint") != fingerprint(current_facts, report.get("llm", {})):
        return ReportLookup("stale", report,
                            "Statistics, prediction, model or prompt changed since generation.")
    if report.get("status") != "ok" or check_report(
            {k: v for k, v in report.get("sections", {}).items()
             if not (k == OUTLOOK and current_facts["prediction"] is None)}, current_facts):
        return ReportLookup("rejected", report, "The report failed the factual checks.")
    return ReportLookup("ok", report)
