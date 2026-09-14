"""Eval page: run the golden rubric suite against the live API (FR-26/27)."""

import json
import os
import sys
from pathlib import Path

import httpx
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from eval.runner import run_all, summarize  # noqa: E402

API_BASE = os.getenv("REGINTEL_API_BASE", "http://localhost:8000")

st.set_page_config(page_title="RegIntel Eval", page_icon="📊")
st.title("Evaluation")

st.caption(
    "Runs eval/golden_cases.json through the live API and scores routing, "
    "tool selection, citations, duplicates, scoping and safety."
)

if st.button("Run golden suite", type="primary"):
    with httpx.Client(base_url=API_BASE, timeout=60) as client:
        try:
            client.get("/ready").raise_for_status()
        except Exception:
            st.error(f"API not reachable at {API_BASE}")
            st.stop()
        progress = st.progress(0.0, text="Running cases…")
        results = run_all(client)
        progress.progress(1.0, text="Done")

    summary = summarize(results)
    c1, c2, c3 = st.columns(3)
    c1.metric("Cases", summary["total"])
    c2.metric("Passed", summary["passed"])
    c3.metric("Pass rate", f"{summary['pass_rate']:.0%}")

    if summary["failed"]:
        st.error("Failed cases")
        for f in summary["failed"]:
            with st.expander(f"❌ {f['id']}"):
                for msg in f["failures"]:
                    st.write("-", msg)
    else:
        st.success("All cases passed")

    with st.expander("Per-case detail"):
        st.json([
            {"id": r.case_id, "passed": r.passed, "nodes": r.nodes_seen, "failures": r.failures}
            for r in results
        ])

st.divider()
st.subheader("Golden cases")
st.json(json.loads((ROOT / "eval" / "golden_cases.json").read_text()))
