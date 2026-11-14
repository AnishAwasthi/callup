#!/usr/bin/env python3
"""Print one player's facts beside the saved summary, as the app will show it.

Use this to review reports before #7's app.py exists. No language model is loaded.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from callup.contract import load
from callup.player_summary import (
    facts_for_player,
    file_version,
    load_prediction_tables,
    load_report,
)
from callup.summary_panel import panel_content


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--player-id", type=int, required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--input", type=Path, default=Path("data/shared/processed/hitter_seasons.csv"))
    parser.add_argument("--predictions", type=Path, default=Path("data/processed/predictions.csv"))
    parser.add_argument("--metrics", type=Path, default=Path("data/processed/model_metrics.json"))
    parser.add_argument("--model", default="ridge")
    parser.add_argument("--report-dir", type=Path, default=Path("data/processed/player_reports"))
    args = parser.parse_args(argv)

    frame = load(args.input)
    predictions, metrics = load_prediction_tables(args.predictions, args.metrics)
    facts = facts_for_player(frame, args.player_id, args.season, predictions=predictions,
                             metrics=metrics, data_version=file_version(args.input),
                             model=args.model)
    player = facts["player"]
    print(f"== {player['name']} ({player['player_id']}), Triple-A {player['season']}\n")
    print("Facts supplied to the model:")
    for item in facts["statistics"] + facts["rates"] + facts["comparisons"]:
        print(f"  {item['label']}: {item['value']}")
    prediction = facts["prediction"] or {}
    for key, value in prediction.items():
        print(f"  {key}: {value if value is not None else 'unavailable'}")
    if not prediction:
        print("  prediction: unavailable")

    content = panel_content(load_report(args.report_dir, args.player_id, args.season, facts))
    print(f"\nSummary status: {content['status']}")
    if content["message"]:
        print(content["message"])
    for heading, body in content["sections"].items():
        print(f"\n{heading}\n  {body}")
    print("\nLimitations:")
    for text in content["limitations"]:
        print(f"  - {text}")
    if content["caption"]:
        print(f"\n{content['caption']}")


if __name__ == "__main__":
    main()
