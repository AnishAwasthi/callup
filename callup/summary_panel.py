"""Player-summary panel for the Streamlit profile page.

The panel only displays saved reports; it never runs a language model. Until #7's app.py
exists, ``scripts/preview_report.py`` shows the same content in the terminal.

TODO(#7): in app.py, after the statistics table for the selected (player_id, season):

    facts = facts_for_player(frame, player_id, season, predictions=..., metrics=...,
                             data_version=file_version(data_path))
    render_summary(st, load_report(REPORT_DIR, player_id, season, facts))
"""
from __future__ import annotations

from callup.player_summary import LIMITATIONS, OUTLOOK, ReportLookup

UNAVAILABLE = {
    "missing": "Summary unavailable: no report has been generated for this player-season.",
    "stale": "Summary unavailable: the statistics, prediction or model changed since this "
             "report was written. Regenerate the reports to update it.",
    "rejected": "Summary unavailable: the generated text failed the factual checks.",
    "invalid": "Summary unavailable: the saved report could not be matched to this player-season.",
}
SECTION_ORDER = ("Strengths", "Concerns", OUTLOOK)


def panel_content(lookup: ReportLookup) -> dict:
    """What to show for one lookup, independent of Streamlit (so it can be tested)."""
    if not lookup.available:
        return {"status": lookup.status, "message": UNAVAILABLE[lookup.status], "sections": {},
                "limitations": list(LIMITATIONS), "caption": ""}
    report = lookup.report
    llm = report.get("llm", {})
    revision = (llm.get("revision") or "unpinned")[:12]
    return {
        "status": "ok",
        "message": "",
        "sections": {h: report["sections"][h] for h in SECTION_ORDER if h in report["sections"]},
        "limitations": report["facts"]["limitations"],
        "caption": (f"Written by {llm.get('model_id', 'unknown model')}@{revision} from the "
                    f"statistics shown, prompt {report.get('prompt_version')}, generated "
                    f"{report.get('generated_at')}. The language model describes the "
                    "statistical model's prediction; it does not make it."),
    }


def render_summary(st, lookup: ReportLookup) -> None:
    """Render with the Streamlit module ``st`` passed in by app.py."""
    content = panel_content(lookup)
    st.subheader("Player summary")
    if content["message"]:
        st.info(content["message"])
    for heading, body in content["sections"].items():
        st.markdown(f"**{heading}**")
        st.write(body)
    st.caption("Limitations: " + " ".join(content["limitations"]))
    if content["caption"]:
        st.caption(content["caption"])
