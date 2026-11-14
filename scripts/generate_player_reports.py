#!/usr/bin/env python3
"""Generate readable player summaries with a local Hugging Face model (issue #10).

Reports are written ahead of time to data/processed/player_reports/; the app only loads them.
Requires `pip install -r requirements-llm.txt` and #4's saved run (scripts/train_models.py).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from callup.contract import load
from callup.player_summary import (
    PROMPT_VERSION,
    build_messages,
    facts_for_player,
    file_version,
    fingerprint,
    load_prediction_tables,
    make_report,
    prompt_sha,
    report_path,
)

DEFAULT_INPUT = Path("data/shared/processed/hitter_seasons.csv")  # TODO(#8): player_features.csv
DEFAULT_REPORTS = Path("data/processed/player_reports")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--predictions", type=Path, default=Path("data/processed/predictions.csv"))
    parser.add_argument("--metrics", type=Path, default=Path("data/processed/model_metrics.json"))
    parser.add_argument("--model", default="ridge", help="Model rows to explain")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument("--llm-model", default=None, help="Hugging Face model id")
    parser.add_argument("--llm-revision", default=None, help="Model commit to pin")
    parser.add_argument("--device", default=None, help="cpu or cuda (default: auto)")
    parser.add_argument("--player-id", type=int)
    parser.add_argument("--season", type=int)
    parser.add_argument("--all", action="store_true",
                        help="All player-seasons, not only those with a saved prediction")
    parser.add_argument("--limit", type=int, help="Stop after this many generated reports")
    parser.add_argument("--force", action="store_true", help="Regenerate current reports too")
    parser.add_argument("--print-prompt", action="store_true",
                        help="Print the prompt for the selected rows without loading a model")
    args = parser.parse_args(argv)
    if (args.player_id is None) != (args.season is None):
        parser.error("--player-id and --season must be given together")
    return args


def select_keys(frame, predictions, args):
    if args.player_id is not None:
        return [(args.player_id, args.season)]
    if args.all:
        return list(frame[["player_id", "season"]].itertuples(index=False, name=None))
    if predictions is None:
        raise SystemExit("No saved predictions found. Run scripts/train_models.py, or pass --all.")
    rows = predictions.loc[predictions.model.eq(args.model), ["player_id", "season"]]
    return sorted(set(rows.itertuples(index=False, name=None)))


def is_current(path, facts, llm_config):
    if not path.exists():
        return False
    report = json.loads(path.read_text(encoding="utf-8"))
    return report.get("fingerprint") == fingerprint(facts, llm_config)


def main(argv=None, generator=None):
    args = parse_args(argv)
    frame = load(args.input)
    data_version = file_version(args.input)
    predictions, metrics = load_prediction_tables(args.predictions, args.metrics)
    keys = select_keys(frame, predictions, args)

    def facts_for(player_id, season):
        return facts_for_player(frame, player_id, season, predictions=predictions,
                                metrics=metrics, data_version=data_version, model=args.model)

    if args.print_prompt:
        for player_id, season in keys[: args.limit]:
            for message in build_messages(facts_for(player_id, season)):
                print(f"--- {message['role']}\n{message['content']}")
        return

    if generator is None:
        from callup.hf_generator import DEFAULT_MODEL, HFGenerator

        generator = HFGenerator(args.llm_model or DEFAULT_MODEL, args.llm_revision, args.device)
    from callup.hf_generator import fingerprint_config

    llm_config = fingerprint_config(generator.config)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    counts = {"ok": 0, "rejected": 0, "skipped_current": 0}
    for player_id, season in keys:
        if args.limit is not None and counts["ok"] + counts["rejected"] >= args.limit:
            break
        facts = facts_for(player_id, season)
        path = report_path(args.report_dir, player_id, season)
        if not args.force and is_current(path, facts, llm_config):
            counts["skipped_current"] += 1
            continue
        text = generator.generate(build_messages(facts))
        report = make_report(facts, text, llm_config,
                             datetime.now(UTC).isoformat(timespec="seconds"), generator.config)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        counts[report["status"]] += 1
        note = "" if report["status"] == "ok" else f" — {'; '.join(report['check_failures'])}"
        print(f"{player_id} {season} {facts['player']['name']}: {report['status']}{note}")

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "input": str(args.input), "input_data_version": data_version,
        "predictions": str(args.predictions), "metrics": str(args.metrics), "model": args.model,
        "llm": llm_config, "llm_runtime": generator.config,
        "prompt_version": PROMPT_VERSION, "prompt_sha": prompt_sha(), "counts": counts,
        "preliminary": True,
    }
    (args.report_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
