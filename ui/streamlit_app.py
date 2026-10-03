"""RegIntel AI — Streamlit demo UI (Phase 1 agentic core).

Run: .venv/bin/streamlit run ui/streamlit_app.py
Requires the API: .venv/bin/uvicorn app.main:app
"""

import json
import os

import httpx
import streamlit as st

API_BASE = os.getenv("REGINTEL_API_BASE", "http://localhost:8000")
EMPLOYEES = {
    "e001 — Asha Verma (IT)": "e001",
    "e002 — Rahul Nair (HR)": "e002",
    "e003 — Meera Joshi (Finance)": "e003",
    "e999 — Admin (IT)": "e999",
}
USECASES = {"IT Support": "it_support", "HR Policy": "hr_support", "Finance": "finance_support"}

st.set_page_config(page_title="RegIntel AI", page_icon="🤖")
st.title("RegIntel AI")


def headers(employee_id: str) -> dict:
    """Auth headers: demo header in stub mode; paste a Bearer token when the
    API runs with REGINTEL_AUTH_MODE=jwt (see scripts/mint_dev_token.py)."""
    h = {"X-Demo-Employee": employee_id}
    token = st.session_state.get("bearer_token", "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def send_feedback(message_id: str, rating: str, employee_id: str) -> None:
    httpx.post(
        f"{API_BASE}/v1/messages/{message_id}/feedback",
        headers=headers(employee_id),
        json={"rating": rating},
        timeout=10,
    )


def api_auth_mode() -> str:
    try:
        return httpx.get(f"{API_BASE}/health", timeout=5).json().get("auth_mode", "stub")
    except Exception:
        return "stub"


def signin_form() -> None:
    """Supabase auth UI — signin/signup/forgot-password, all through our API.
    On success the access token lands in st.session_state.bearer_token."""
    if st.session_state.get("bearer_token"):
        me = {}
        try:
            me = httpx.get(
                f"{API_BASE}/v1/auth/me", headers=headers(""), timeout=10
            ).json()
        except Exception:
            pass
        if me.get("employee_id"):
            st.success(f"Signed in as {me['name']} ({me['employee_id']})")
        if st.button("Sign out"):
            httpx.post(f"{API_BASE}/v1/auth/signout", headers=headers(""), timeout=10)
            st.session_state.pop("bearer_token", None)
            st.session_state.pop("conversation_id", None)
            st.session_state.pop("messages", None)
            st.rerun()
        return

    tab_in, tab_up, tab_forgot = st.tabs(["Sign in", "Sign up", "Forgot"])
    with tab_in:
        with st.form("signin"):
            email = st.text_input("Email", key="si_email")
            password = st.text_input("Password", type="password", key="si_pw")
            if st.form_submit_button("Sign in"):
                try:
                    resp = httpx.post(
                        f"{API_BASE}/v1/auth/signin",
                        json={"email": email, "password": password},
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        body = resp.json()
                        st.session_state.bearer_token = body["access_token"]
                        if body.get("approved"):
                            st.rerun()
                        else:
                            st.warning(body.get("message", "Pending approval."))
                    else:
                        st.error(resp.json().get("detail", "Sign-in failed"))
                except Exception as exc:
                    st.error(f"Auth service unreachable: {exc}")
    with tab_up:
        with st.form("signup"):
            st.text_input("Name", key="su_name")
            st.text_input("Email", key="su_email")
            st.text_input("Password (min 8 chars)", type="password", key="su_pw")
            if st.form_submit_button("Create account"):
                try:
                    resp = httpx.post(
                        f"{API_BASE}/v1/auth/signup",
                        json={
                            "email": st.session_state.su_email,
                            "password": st.session_state.su_pw,
                            "name": st.session_state.su_name,
                        },
                        timeout=15,
                    )
                    if resp.status_code in (200, 201):
                        st.success(resp.json().get("message", "Account created."))
                    else:
                        st.error(resp.json().get("detail", "Sign-up failed"))
                except Exception as exc:
                    st.error(f"Auth service unreachable: {exc}")
    with tab_forgot:
        with st.form("forgot"):
            st.text_input("Email", key="fp_email")
            if st.form_submit_button("Send reset link"):
                try:
                    httpx.post(
                        f"{API_BASE}/v1/auth/forgot-password",
                        json={"email": st.session_state.fp_email},
                        timeout=15,
                    )
                    st.success("If that email is registered, a reset link is on its way.")
                except Exception as exc:
                    st.error(f"Auth service unreachable: {exc}")


with st.sidebar:
    st.header("Session")
    mode = api_auth_mode()
    if mode == "supabase":
        signin_form()
        if not st.session_state.get("bearer_token"):
            st.info("Sign in to use the assistant.")
            st.stop()
        employee_id = ""  # identity comes from the token, not a picker
    else:
        employee_label = st.selectbox("Employee", list(EMPLOYEES))
        employee_id = EMPLOYEES[employee_label]
        if mode == "jwt":
            st.text_input(
                "Bearer token (JWT mode only)",
                key="bearer_token",
                type="password",
                help="Only needed when the API runs with REGINTEL_AUTH_MODE=jwt",
            )
    usecase_label = st.selectbox("Use case", list(USECASES))
    usecase_id = USECASES[usecase_label]

    # Switching employee or use case mid-chat must reset the session —
    # conversations are owned per-employee, so reusing the old id 403s.
    if st.session_state.get("active_employee") != employee_id or st.session_state.get(
        "active_usecase"
    ) != usecase_id:
        st.session_state.active_employee = employee_id
        st.session_state.active_usecase = usecase_id
        st.session_state.pop("conversation_id", None)
        st.session_state.pop("messages", None)
        st.rerun()

    if st.button("New conversation"):
        st.session_state.pop("conversation_id", None)
        st.session_state.pop("messages", None)
        st.rerun()
    st.caption(f"API: {API_BASE} · auth: {mode}")

    st.subheader("Conversations")
    convs: list = []
    try:
        resp = httpx.get(
            f"{API_BASE}/v1/conversations", headers=headers(employee_id), timeout=10
        )
        if resp.status_code == 200:
            convs = resp.json()
        elif resp.status_code in (401, 403):
            st.warning("Not authenticated — the API requires a valid token.")
    except Exception:
        pass
    options = {"(none)": None} | {
        f"{c['title'][:28]} · {c['updated_at'][:10]}": c["conversation_id"] for c in convs
    }
    picked = st.selectbox("Resume", list(options))
    if options[picked] and options[picked] != st.session_state.get("conversation_id"):
        conv_id = options[picked]
        resp = httpx.get(
            f"{API_BASE}/v1/conversations/{conv_id}", headers=headers(employee_id), timeout=10
        )
        if resp.status_code != 200:
            st.error(f"Could not load conversation: {resp.status_code}")
            st.stop()
        detail = resp.json()
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
            if stream.status_code != 200:
                raw = stream.read().decode("utf-8", "replace")
                try:
                    raw = json.loads(raw).get("detail", raw)
                except Exception:
                    pass
                st.session_state.pop("conversation_id", None)
                st.session_state.pop("messages", None)
                st.error(
                    f"API error {stream.status_code}: {raw} — "
                    "session cleared; send your message again."
                )
                st.stop()
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
