"""RegIntel AI — Streamlit demo UI (Phase 1 agentic core).

Run: .venv/bin/streamlit run ui/streamlit_app.py
Requires the API: .venv/bin/uvicorn app.main:app
"""

import json
import os

import httpx
import streamlit as st

API_BASE = os.getenv("REGINTEL_API_BASE", "http://localhost:8000")
EMPLOYEES = {"e001 — Asha Verma (IT)": "e001", "e002 — Rahul Nair (HR)": "e002", "e999 — Admin (IT)": "e999"}
USECASES = {"IT Support": "it_support", "HR Policy": "hr_support"}

st.set_page_config(page_title="RegIntel AI", page_icon="🤖")
st.title("RegIntel AI")


def headers(employee_id: str) -> dict:
    return {"X-Demo-Employee": employee_id}


def send_feedback(message_id: str, rating: str, employee_id: str) -> None:
    httpx.post(
        f"{API_BASE}/v1/messages/{message_id}/feedback",
        headers=headers(employee_id),
        json={"rating": rating},
        timeout=10,
    )


with st.sidebar:
    st.header("Session")
    employee_label = st.selectbox("Employee", list(EMPLOYEES))
    employee_id = EMPLOYEES[employee_label]
    usecase_label = st.selectbox("Use case", list(USECASES))
    usecase_id = USECASES[usecase_label]
    if st.button("New conversation"):
        st.session_state.pop("conversation_id", None)
        st.session_state.pop("messages", None)
        st.rerun()
    st.caption(f"API: {API_BASE}")

    st.subheader("Conversations")
    try:
        convs = httpx.get(
            f"{API_BASE}/v1/conversations", headers=headers(employee_id), timeout=10
        ).json()
    except Exception:
        convs = []
    options = {"(none)": None} | {
        f"{c['title'][:28]} · {c['updated_at'][:10]}": c["conversation_id"] for c in convs
    }
    picked = st.selectbox("Resume", list(options))
    if options[picked] and options[picked] != st.session_state.get("conversation_id"):
        conv_id = options[picked]
        detail = httpx.get(
            f"{API_BASE}/v1/conversations/{conv_id}", headers=headers(employee_id), timeout=10
        ).json()
        st.session_state.conversation_id = conv_id
        st.session_state.messages = [
            {
                "role": m["role"],
                "content": m["content"],
                "citations": m.get("citations", []),
                "message_id": m["message_id"],
            }
            for m in detail["messages"]
        ]
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

try:
    ready = httpx.get(f"{API_BASE}/ready", timeout=10).json()
    if not ready.get("ready"):
        st.warning(f"API not fully ready: {ready}")
except Exception:
    st.error(f"Cannot reach API at {API_BASE}. Start it with: .venv/bin/uvicorn app.main:app")
    st.stop()


def render_message(msg: dict, idx: int) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        for c in msg.get("citations", []):
            with st.expander(f"[{c['citation_id']}] {c['title']} — {c.get('page_section') or ''}"):
                st.caption(
                    f"{c['source_system']} · {c.get('source_ref') or ''} · v{c.get('document_version')}"
                )
                if c.get("excerpt"):
                    st.write(c["excerpt"])
                if c.get("retrieval_score") is not None:
                    st.caption(
                        f"retrieval: {c['retrieval_score']} · rerank: {c.get('rerank_score')}"
                    )
        if msg["role"] == "assistant" and msg.get("message_id"):
            col1, col2, _ = st.columns([0.07, 0.07, 0.86])
            if col1.button("👍", key=f"up{idx}"):
                send_feedback(msg["message_id"], "up", employee_id)
                st.toast("Feedback recorded")
            if col2.button("👎", key=f"down{idx}"):
                send_feedback(msg["message_id"], "down", employee_id)
                st.toast("Feedback recorded")


for i, msg in enumerate(st.session_state.messages):
    render_message(msg, i)

if prompt := st.chat_input("Ask something…"):
    st.session_state.messages.append({"role": "user", "content": prompt, "citations": []})
    with st.chat_message("user"):
        st.write(prompt)

    if st.session_state.conversation_id is None:
        resp = httpx.post(
            f"{API_BASE}/v1/conversations",
            headers=headers(employee_id),
            json={"usecase_id": usecase_id},
            timeout=30,
        )
        if resp.status_code != 201:
            st.error(f"Failed to create conversation: {resp.text}")
            st.stop()
        st.session_state.conversation_id = resp.json()["conversation_id"]

    with st.chat_message("assistant"):
        status_box = st.empty()
        answer_box = st.empty()
        answer, usage, citations, message_id = "", None, [], None
        seen_nodes: list[str] = []

        with httpx.stream(
            "POST",
            f"{API_BASE}/v1/conversations/{st.session_state.conversation_id}/messages:stream",
            headers=headers(employee_id),
            json={"content": prompt},
            timeout=60,
        ) as stream:
            for line in stream.iter_lines():
                if not line:
                    continue
                event = json.loads(line)
                match event["type"]:
                    case "status":
                        node = event["data"].get("detail", "")
                        if node and node not in seen_nodes:
                            seen_nodes.append(node)
                        status_box.caption("⚙️ " + " → ".join(seen_nodes))
                    case "token":
                        answer += event["data"]["text"]
                        answer_box.markdown(answer)
                    case "citation":
                        citations.append(event["data"])
                    case "usage":
                        usage = event["data"]
                    case "complete":
                        message_id = event["data"]["message_id"]
                    case "error":
                        st.error(event["data"]["message"])

        status_box.empty()
        for c in citations:
            with st.expander(f"[{c['citation_id']}] {c['title']} — {c.get('page_section') or ''}"):
                st.caption(
                    f"{c['source_system']} · {c.get('source_ref') or ''} · v{c.get('document_version')}"
                )
                if c.get("excerpt"):
                    st.write(c["excerpt"])
                if c.get("rerank_score") is not None:
                    st.caption(
                        f"retrieval: {c.get('retrieval_score')} · rerank: {c['rerank_score']}"
                    )
        if usage:
            st.caption(f"model={usage['model']} · tokens={usage['total_tokens']} · {usage['latency_ms']}ms")

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
                "citations": citations,
                "message_id": message_id,
            }
        )
        st.rerun()
