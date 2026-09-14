"""RegIntel AI — Streamlit demo UI (Phase 0 walking skeleton).

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
st.title("RegIntel AI — Phase 0 Demo")

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
            f"{API_BASE}/v1/conversations",
            headers={"X-Demo-Employee": employee_id},
            timeout=10,
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
            f"{API_BASE}/v1/conversations/{conv_id}",
            headers={"X-Demo-Employee": employee_id},
            timeout=10,
        ).json()
        st.session_state.conversation_id = conv_id
        st.session_state.messages = [
            {"role": m["role"], "content": m["content"], "correlation_id": m.get("correlation_id")}
            for m in detail["messages"]
        ]
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

headers = {"X-Demo-Employee": employee_id}


def api_get(path: str):
    return httpx.get(f"{API_BASE}{path}", headers=headers, timeout=10)


def api_post(path: str, payload: dict):
    return httpx.post(f"{API_BASE}{path}", headers=headers, json=payload, timeout=30)


try:
    ready = api_get("/ready").json()
    if not ready.get("ready"):
        st.warning(f"API not fully ready: {ready}")
except Exception:
    st.error(f"Cannot reach API at {API_BASE}. Start it with: .venv/bin/uvicorn app.main:app")
    st.stop()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("correlation_id"):
            with st.expander("debug"):
                st.code(f"correlation_id: {msg['correlation_id']}")

if prompt := st.chat_input("Ask something…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    if st.session_state.conversation_id is None:
        resp = api_post("/v1/conversations", {"usecase_id": usecase_id})
        if resp.status_code != 201:
            st.error(f"Failed to create conversation: {resp.text}")
            st.stop()
        st.session_state.conversation_id = resp.json()["conversation_id"]

    with st.chat_message("assistant"):
        status_box = st.empty()
        answer_box = st.empty()
        answer, usage, correlation_id, error = "", None, None, None

        with httpx.stream(
            "POST",
            f"{API_BASE}/v1/conversations/{st.session_state.conversation_id}/messages:stream",
            headers=headers,
            json={"content": prompt},
            timeout=60,
        ) as stream:
            correlation_id = stream.headers.get("x-correlation-id")
            for line in stream.iter_lines():
                if not line:
                    continue
                event = json.loads(line)
                match event["type"]:
                    case "status":
                        status_box.caption(f"⚙️ {event['data']['stage']}: {event['data'].get('detail', '')}")
                    case "token":
                        answer += event["data"]["text"]
                        answer_box.write(answer)
                    case "usage":
                        usage = event["data"]
                    case "error":
                        error = event["data"]["message"]
                        st.error(error)
                    case "complete":
                        pass

        status_box.empty()
        if not error and usage:
            st.caption(f"model={usage['model']} · tokens={usage['total_tokens']} · {usage['latency_ms']}ms")
        if correlation_id:
            with st.expander("debug"):
                st.code(f"correlation_id: {correlation_id}")

        st.session_state.messages.append(
            {"role": "assistant", "content": answer or error, "correlation_id": correlation_id}
        )
