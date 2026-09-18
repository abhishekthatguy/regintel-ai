"""Memory/state + safety/validation behaviors from the project requirements:

- Retain information across turns (offered actions, prior message fields).
- Validate required information before writes; ask when it's missing.
- Never invent ticket information; dedupe prevents double writes.
- Explicit confirmation still gates every write.
"""

import json as _json


def _conv(client, headers, usecase="it_support"):
    r = client.post("/v1/conversations", headers=headers, json={"usecase_id": usecase})
    assert r.status_code == 201
    return r.json()["conversation_id"]


def _send(client, headers, cid, msg):
    lines, text = [], ""
    with client.stream(
        "POST", f"/v1/conversations/{cid}/messages:stream",
        headers=headers, json={"content": msg},
    ) as r:
        assert r.status_code == 200
        for line in r.iter_lines():
            if not line:
                continue
            lines.append(line)
            ev = _json.loads(line)
            if ev["type"] == "token":
                text += ev["data"]["text"]
    return lines, text


def _h(auth_headers, employee="e001"):
    h = dict(auth_headers)
    h["X-Demo-Employee"] = employee
    return h


# --- offered-action memory (the requirement's example flow) -----------------


def test_yes_to_offer_runs_ticket_flow(client, auth_headers):
    """Knowledge answer offers ticket creation; 'yes' must act on that
    offer — not be treated as a fresh knowledge query."""
    h = _h(auth_headers)
    cid = _conv(client, h)
    _send(client, h, cid, "my monitor keeps flickering")
    _, text = _send(client, h, cid, "yes")
    # Fields mined from the earlier turn -> straight to the confirm gate.
    assert "Confirm" in text
    assert "knowledge base" not in text


def test_no_to_offer_declines_politely(client, auth_headers):
    h = _h(auth_headers)
    cid = _conv(client, h)
    _send(client, h, cid, "my monitor keeps flickering")
    _, text = _send(client, h, cid, "no")
    assert "won't do that" in text or "No problem" in text


def test_offer_flow_reaches_confirmation(client, auth_headers):
    """Full requirement example: issue -> yes -> confirm -> yes -> write."""
    h = _h(auth_headers)
    cid = _conv(client, h)
    _send(client, h, cid, "my keyboard keys are sticking")
    _, t2 = _send(client, h, cid, "yes")
    assert "hardware" in t2
    _, t3 = _send(client, h, cid, "yes")
    assert "TCK-" in t3


def test_offer_flow_dedupes_existing_ticket(client, auth_headers):
    """'I have a VPN issue' + 'yes' must dedupe against the open VPN
    ticket (TCK-1001) instead of creating a second one."""
    h = _h(auth_headers)
    cid = _conv(client, h)
    _send(client, h, cid, "I have a VPN issue")
    _, text = _send(client, h, cid, "yes")
    assert "already have" in text or "TCK-1001" in text


def test_new_question_clears_offer(client, auth_headers):
    """An unrelated next turn must clear the offer, not confirm it."""
    h = _h(auth_headers)
    cid = _conv(client, h)
    _send(client, h, cid, "my monitor keeps flickering")
    _, text = _send(client, h, cid, "what is the leave policy")
    assert "knowledge base" in text
    assert "Confirm" not in text


# --- multi-turn field memory ------------------------------------------------


def test_fields_mined_from_prior_turn(client, auth_headers):
    """'create a ticket for it' after describing the issue must reuse the
    earlier description instead of re-asking for it."""
    h = _h(auth_headers)
    cid = _conv(client, h)
    _send(client, h, cid, "my laptop screen flickers badly")
    _, text = _send(client, h, cid, "create a ticket for it")
    assert "Confirm" in text
    assert "still need" not in text


def test_missing_fields_still_clarifies(client, auth_headers):
    """No prior substance -> the agent must ask, not invent fields."""
    h = _h(auth_headers)
    cid = _conv(client, h)
    _, text = _send(client, h, cid, "create a ticket")
    assert "still need" in text
    assert "Confirm" not in text


def test_command_history_not_mined_as_description(client, auth_headers):
    """A past 'show my tickets' command must not become the new ticket's
    description."""
    h = _h(auth_headers)
    cid = _conv(client, h)
    _send(client, h, cid, "show my tickets")
    _, text = _send(client, h, cid, "create a ticket")
    assert "still need" in text


# --- never invent / safety ---------------------------------------------------


def test_nonexistent_ticket_not_invented(client, auth_headers):
    """Asking about TCK-9999 must not fabricate it — the response only
    ever lists real tickets."""
    h = _h(auth_headers)
    cid = _conv(client, h)
    _, text = _send(client, h, cid, "what is the status of TCK-9999")
    assert "TCK-9999" not in text
    assert "TCK-1001" in text  # real tickets are shown instead


def test_pending_confirm_beats_offer(client, auth_headers):
    """'yes' while a write awaits confirmation confirms THAT write."""
    h = _h(auth_headers)
    cid = _conv(client, h)
    _, t1 = _send(client, h, cid, "create a ticket my headset mic is dead")
    assert "Confirm" in t1
    _, t2 = _send(client, h, cid, "yes")
    assert "created" in t2.lower()
    assert "TCK-" in t2


def test_gibberish_stays_honest(client, auth_headers):
    h = _h(auth_headers)
    cid = _conv(client, h)
    _, text = _send(client, h, cid, "asdf qwerty zxcv")
    assert "won't guess" in text or "couldn't find" in text


# --- the requirement's literal example exchange ------------------------------


def test_employee_id_acknowledged_not_retrieved(client, auth_headers):
    """'EMP1024' must get a profile response, not a knowledge lookup."""
    h = _h(auth_headers)
    cid = _conv(client, h)
    _, text = _send(client, h, cid, "EMP1024")
    assert "signed in" in text or "profile" in text.lower()
    assert "knowledge base" not in text


def test_typed_id_cannot_switch_identity(client, auth_headers):
    """Typing another employee's ID must not switch the session identity —
    it surfaces the real signed-in profile instead."""
    h = _h(auth_headers)  # signed in as e001
    cid = _conv(client, h)
    _, text = _send(client, h, cid, "EMP1024")
    assert "e001" in text  # real identity is surfaced
    _, text = _send(client, h, cid, "show my tickets")
    assert "TCK-1001" in text  # still e001's tickets, not EMP1024's


def test_matching_id_confirms_profile(client, auth_headers):
    h = _h(auth_headers)
    cid = _conv(client, h)
    _, text = _send(client, h, cid, "my employee id is e001")
    assert "found your profile" in text.lower() or "signed in" in text


def test_profile_offer_yes_checks_tickets(client, auth_headers):
    """The full example: ID -> profile + offer -> 'yes' -> ticket list."""
    h = _h(auth_headers)
    cid = _conv(client, h)
    _, t1 = _send(client, h, cid, "EMP1024")
    assert "existing tickets" in t1
    _, t2 = _send(client, h, cid, "yes")
    assert "TCK-1001" in t2
