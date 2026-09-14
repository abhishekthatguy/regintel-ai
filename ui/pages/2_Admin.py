"""Admin page: use-case config, conversations, tickets (Phase 1, FR-27)."""

import os
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

st.set_page_config(page_title="RegIntel Admin", page_icon="🛠️")
st.title("Admin")

ROOT = Path(__file__).resolve().parent.parent.parent
DB = Path(os.getenv("REGINTEL_DB_PATH", ROOT / "data" / "regintel.db"))
USECASE_DIR = Path(os.getenv("REGINTEL_USECASE_DIR", ROOT / "data" / "usecases"))
KNOWLEDGE_DIR = Path(os.getenv("REGINTEL_KNOWLEDGE_DIR", ROOT / "data" / "knowledge"))

tab_config, tab_data, tab_corpus = st.tabs(["Use-case config", "Data", "Corpus"])

with tab_config:
    for path in sorted(USECASE_DIR.glob("*.yaml")):
        cfg = yaml.safe_load(path.read_text())
        with st.expander(f"{cfg['usecase_id']} — {cfg['name']} (v{cfg['version']})"):
            st.json(cfg)

with tab_data:
    if DB.exists():
        conn = sqlite3.connect(DB)
        for table, label in [
            ("conversations", "Conversations"),
            ("messages", "Messages"),
            ("tickets", "Tickets"),
            ("feedback", "Feedback"),
            ("employees", "Employees"),
        ]:
            st.subheader(label)
            try:
                df = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 50", conn)
                st.dataframe(df, use_container_width=True)
            except Exception as exc:
                st.caption(f"({exc})")
        conn.close()
    else:
        st.info(f"No database at {DB} — run scripts/seed_db.py")

with tab_corpus:
    for path in sorted(KNOWLEDGE_DIR.rglob("*.md")):
        raw = path.read_text()
        meta = {}
        if raw.startswith("---"):
            meta = yaml.safe_load(raw.split("---")[1])
        with st.expander(f"{meta.get('doc_id', path.stem)} — {meta.get('title', '')}"):
            st.caption(f"dept={meta.get('department')} · acl={meta.get('acl')} · v{meta.get('version')}")
            st.markdown(raw.split("---", 2)[-1])
