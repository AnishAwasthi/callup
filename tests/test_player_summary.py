import json
from pathlib import Path

import pandas as pd
import pytest

from callup import player_summary as ps
from callup.contract import load
from callup.summary_panel import UNAVAILABLE, panel_content, render_summary
from scripts import generate_player_reports

SAMPLE = Path("data/sample/hitter_seasons.csv")
LLM = {"model_id": "fake/model", "revision": "abc123", "seed": 0, "generation": {"do_sample": False}}

GOOD = """Strengths
He walked in 8.0% of his 200 Triple-A plate appearances, the 62nd percentile among 2024 study hitters.

Concerns
His home-run rate of 2.5% was in the 38th percentile.

MLB outlook
The statistical model estimates a 2025 MLB wOBA of .318, slightly below the training-average baseline of .322. This result is preliminary.
"""
GOOD_NO_PREDICTION = """**Strengths:** He walked in 8.3% of his plate appearances.
**Concerns:** He struck out in 16.7% of his plate appearances.
"""


@pytest.fixture
def frame():
    return load(SAMPLE)


@pytest.fixture
def run():
    """Invented saved model run in #4's predictions.csv / model_metrics.json format."""
    common = {"split": "test", "outcome_year": 2025, "data_version": "sha256:data",
              "code_version": "abc", "code_dirty": False}
    predictions = pd.DataFrame([
        {"player_id": 9000011, "season": 2024, "model": "training_average", "y_true": 0.31,
         "y_pred": 0.322, **common},
        {"player_id": 9000012, "season": 2024, "model": "training_average", "y_true": 0.335,
         "y_pred": 0.322, **common},
        {"player_id": 9000011, "season": 2024, "model": "ridge", "y_true": 0.31,
         "y_pred": 0.329, **common},
        {"player_id": 9000012, "season": 2024, "model": "ridge", "y_true": 0.335,
         "y_pred": 0.318, **common},
    ])
    version = {"data_version": "sha256:data", "code_version": "abc"}
    metrics = {"models": {"ridge": version, "training_average": version}}
    return predictions, metrics


def facts(frame, run, player_id=9000012, season=2024, data_version="sha256:input"):
    predictions, metrics = run
    return ps.facts_for_player(frame, player_id, season, predictions=predictions,
                               metrics=metrics, data_version=data_version)


def write(tmp_path, report):
    path = ps.report_path(tmp_path, report["player_id"], report["season"])
    path.write_text(json.dumps(report))
    return path


def test_facts_use_saved_prediction_and_formatted_values(frame, run):
    f = facts(frame, run)
    assert f["player"] == {"player_id": 9000012, "name": "Synthetic Hitter 9000012",
                           "season": 2024, "outcome_year": 2025}
    assert {r["label"]: r["value"] for r in f["rates"]}[
        "Triple-A walk rate (walks / plate appearances)"] == "8.0%"
    assert f["prediction"]["predicted_next_season_mlb_woba"] == ".318"
    assert f["prediction"]["training_average_baseline_woba"] == ".322"
    assert f["prediction"]["observed_provisional_mlb_woba"] == ".335"
    assert [c["value"].split()[0] for c in f["comparisons"]] == ["62nd", "62nd", "62nd", "38th"]


def test_valid_report_passes(frame, run):
    report = ps.make_report(facts(frame, run), GOOD, LLM, "2026-11-13T00:00:00+00:00")
    assert report["check_failures"] == []
    assert report["status"] == "ok"
    assert list(report["sections"]) == ["Strengths", "Concerns", "MLB outlook"]


@pytest.mark.parametrize("bad, reason", [
    ("8.0% of his 212 Triple-A", "number 212 is not in the supplied facts"),
    ("8.0% of his 200 Triple-A, despite a hamstring injury,", "injury or health"),
    ("8.0% of his 200 Triple-A, thanks to sound swing mechanics,", "mechanics or swing"),
    ("8.0% of his 200 Triple-A, which scouts praised,", "scouting opinion"),
])
def test_invented_numbers_and_topics_are_rejected(frame, run, bad, reason):
    text = GOOD.replace("8.0% of his 200 Triple-A", bad)
    report = ps.make_report(facts(frame, run), text, LLM, "t")
    assert report["status"] == "rejected"
    assert any(reason in failure for failure in report["check_failures"]), report["check_failures"]


def test_peer_comparison_rejected_without_comparison_facts(frame, run):
    f = facts(frame, run) | {"comparisons": []}
    text = GOOD.replace(", the 62nd percentile among 2024 study hitters", ", well above average")
    text = text.replace(" was in the 38th percentile", " is 2.5%")
    failures = ps.check_report(ps.parse_sections(text, ps.headings_for(f)), f)
    assert failures == ["Strengths: comparison with other hitters, but none was supplied"]


def test_wrong_baseline_direction_and_missing_prediction_rejected(frame, run):
    f = facts(frame, run)
    wrong = GOOD.replace("slightly below", "above")
    assert "wrong direction" in " ".join(ps.make_report(f, wrong, LLM, "t")["check_failures"])
    vague = GOOD.replace("a 2025 MLB wOBA of .318, ", "a modest 2025 MLB wOBA, ")
    assert "does not state the saved prediction" in " ".join(
        ps.make_report(f, vague, LLM, "t")["check_failures"])


def test_missing_heading_rejected(frame, run):
    report = ps.make_report(facts(frame, run), GOOD.replace("Concerns\n", ""), LLM, "t")
    assert report["status"] == "rejected"
    assert "Expected headings" in report["check_failures"][0]


def test_no_prediction_gets_fixed_outlook_without_numbers(frame, run):
    f = facts(frame, run, player_id=9000001, season=2023)
    assert f["prediction"] is None
    assert "MLB outlook" not in ps.build_messages(f)[0]["content"].split("headings")[1].split(".")[0]
    report = ps.make_report(f, GOOD_NO_PREDICTION, LLM, "t")
    assert report["status"] == "ok", report["check_failures"]
    assert report["sections"]["MLB outlook"] == ps.NO_PREDICTION_OUTLOOK
    # An LLM-written outlook is not accepted when there is no prediction.
    assert ps.make_report(f, GOOD_NO_PREDICTION + "MLB outlook\nA .330 wOBA.", LLM,
                          "t")["status"] == "rejected"


@pytest.mark.parametrize("change", ["data", "prediction", "prompt", "llm"])
def test_fingerprint_changes_with_inputs(frame, run, monkeypatch, change):
    f = facts(frame, run)
    before = ps.fingerprint(f, LLM)
    llm = LLM
    if change == "data":
        f = facts(frame, run, data_version="sha256:other")
    elif change == "prediction":
        run[0].loc[run[0].model.eq("ridge") & run[0].player_id.eq(9000012), "y_pred"] = 0.3
        f = facts(frame, run)
    elif change == "prompt":
        monkeypatch.setattr(ps, "PROMPT_VERSION", "v2")
    else:
        llm = LLM | {"revision": "def456"}
    assert ps.fingerprint(f, llm) != before


def test_load_report_states(tmp_path, frame, run):
    f = facts(frame, run)
    assert ps.load_report(tmp_path, 9000012, 2024, f).status == "missing"
    write(tmp_path, ps.make_report(f, GOOD, LLM, "t"))
    assert ps.load_report(tmp_path, 9000012, 2024, f).status == "ok"
    assert ps.load_report(tmp_path, 9000012, 2024, facts(frame, run, data_version="x")).status == "stale"
    write(tmp_path, ps.make_report(f, GOOD.replace("200", "212"), LLM, "t"))
    assert ps.load_report(tmp_path, 9000012, 2024, f).status == "rejected"


def test_load_report_never_returns_another_players_file(tmp_path, frame, run):
    other = facts(frame, run, player_id=9000011)
    report = ps.make_report(other, GOOD, LLM, "t")
    ps.report_path(tmp_path, 9000012, 2024).write_text(json.dumps(report))  # renamed into place
    lookup = ps.load_report(tmp_path, 9000012, 2024, facts(frame, run))
    assert lookup.status == "invalid" and not lookup.available
    assert ps.load_report(tmp_path, 9000011, 2024, other).status == "missing"


def test_hand_edited_sections_fail_on_load(tmp_path, frame, run):
    f = facts(frame, run)
    report = ps.make_report(f, GOOD, LLM, "t")
    report["sections"]["Concerns"] = "He has a lingering injury."
    write(tmp_path, report)
    assert ps.load_report(tmp_path, 9000012, 2024, f).status == "rejected"


def test_mixed_model_runs_raise(frame, run):
    predictions, metrics = run
    metrics["models"]["ridge"]["code_version"] = "different"
    with pytest.raises(ValueError, match="different runs"):
        facts(frame, (predictions, metrics))


def test_panel_shows_sections_or_unavailable_message(tmp_path, frame, run):
    f = facts(frame, run)
    missing = panel_content(ps.load_report(tmp_path, 9000012, 2024, f))
    assert missing["message"] == UNAVAILABLE["missing"] and missing["sections"] == {}
    write(tmp_path, ps.make_report(f, GOOD, LLM, "t"))
    content = panel_content(ps.load_report(tmp_path, 9000012, 2024, f))
    assert list(content["sections"]) == ["Strengths", "Concerns", "MLB outlook"]
    assert "fake/model@abc123" in content["caption"]

    class FakeStreamlit:
        def __init__(self):
            self.calls = []

        def __getattr__(self, name):
            return lambda *args: self.calls.append((name, *args))

    st = FakeStreamlit()
    render_summary(st, ps.load_report(tmp_path, 9000012, 2024, f))
    assert ("markdown", "**MLB outlook**") in st.calls


class FakeGenerator:
    config = LLM | {"device": "cpu"}

    def __init__(self):
        self.prompts = []

    def generate(self, messages):
        self.prompts.append(messages)
        return GOOD if "200" in messages[1]["content"].split("plate appearances: ")[1][:4] else ""


def test_script_generates_saved_rows_and_skips_current(tmp_path, run):
    predictions, metrics = run
    predictions.to_csv(tmp_path / "predictions.csv", index=False)
    (tmp_path / "model_metrics.json").write_text(json.dumps(metrics))
    reports = tmp_path / "reports"
    argv = ["--input", str(SAMPLE), "--predictions", str(tmp_path / "predictions.csv"),
            "--metrics", str(tmp_path / "model_metrics.json"), "--report-dir", str(reports)]
    generator = FakeGenerator()
    generate_player_reports.main(argv, generator=generator)
    assert sorted(p.name for p in reports.iterdir()) == [
        "9000011_2024.json", "9000012_2024.json", "manifest.json"]
    statuses = {p.stem: json.loads(p.read_text())["status"] for p in reports.glob("9*.json")}
    assert statuses == {"9000011_2024": "rejected", "9000012_2024": "ok"}
    manifest = json.loads((reports / "manifest.json").read_text())
    assert manifest["llm"] == LLM and manifest["prompt_version"] == ps.PROMPT_VERSION
    generate_player_reports.main(argv, generator=generator)
    assert len(generator.prompts) == 2  # unchanged inputs are not regenerated
