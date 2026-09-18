"""Generate docs/submission/RegIntel-AI-Pitch-Deck.pptx.

Source of truth for slide content is docs/pitch-deck.md — keep the two in
sync. Regenerate: `.venv/bin/python scripts/build_pitch_deck.py`
(requires `pip install python-pptx`).
"""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "submission" / "RegIntel-AI-Pitch-Deck.pptx"

BG = RGBColor(0x0F, 0x17, 0x2A)       # slate-950
CARD = RGBColor(0x1E, 0x29, 0x3B)     # slate-800
ACCENT = RGBColor(0x81, 0x8C, 0xF8)   # indigo-400
TEXT = RGBColor(0xE2, 0xE8, 0xF0)     # slate-200
MUTED = RGBColor(0x94, 0xA3, 0xB8)    # slate-400
GREEN = RGBColor(0x4A, 0xDE, 0x80)    # green-400

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def slide():
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = BG
    return s


def box(s, left, top, width, height):
    b = s.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    b.text_frame.word_wrap = True
    return b.text_frame


def para(tf, text, size=18, color=TEXT, bold=False, first=False, space_after=6, font="Calibri"):
    p = tf.paragraphs[0] if first and not tf.paragraphs[0].runs else tf.add_paragraph()
    p.text = text
    p.space_after = Pt(space_after)
    for r in p.runs:
        r.font.size = Pt(size)
        r.font.color.rgb = color
        r.font.bold = bold
        r.font.name = font
    return p


def title_slide(title, subtitle, footer):
    s = slide()
    tf = box(s, 0.9, 2.4, 11.5, 3)
    para(tf, title, 54, TEXT, bold=True, first=True)
    para(tf, subtitle, 24, ACCENT, space_after=18)
    para(tf, footer, 16, MUTED)
    return s


def content_slide(title, bullets, subtitle=None):
    s = slide()
    tf = box(s, 0.9, 0.5, 11.5, 1.2)
    para(tf, title, 34, TEXT, bold=True, first=True)
    if subtitle:
        para(tf, subtitle, 15, MUTED)
    bar = s.shapes.add_shape(1, Inches(0.9), Inches(1.55), Inches(1.4), Pt(3))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    tf = box(s, 0.9, 1.9, 11.6, 5.2)
    for i, (head, body) in enumerate(bullets):
        para(tf, head, 19, ACCENT if head.startswith("•") is False else TEXT, bold=True,
             first=(i == 0), space_after=2)
        if body:
            for line in body:
                para(tf, f"    {line}", 15, TEXT, space_after=8)
        else:
            tf.paragraphs[-1].space_after = Pt(10)
    return s


def mono_slide(title, code, note=None):
    s = slide()
    tf = box(s, 0.9, 0.5, 11.5, 1.0)
    para(tf, title, 34, TEXT, bold=True, first=True)
    card = s.shapes.add_shape(1, Inches(0.9), Inches(1.5), Inches(11.5), Inches(4.9))
    card.fill.solid()
    card.fill.fore_color.rgb = CARD
    card.line.color.rgb = RGBColor(0x33, 0x41, 0x55)
    tf = box(s, 1.3, 1.75, 10.7, 4.5)
    for i, line in enumerate(code.split("\n")):
        para(tf, line, 14, GREEN, first=(i == 0), space_after=1, font="Menlo")
    if note:
        tf2 = box(s, 0.9, 6.55, 11.5, 0.7)
        para(tf2, note, 13, MUTED, first=True)
    return s


def table_slide(title, headers, rows, subtitle=None):
    s = slide()
    tf = box(s, 0.9, 0.5, 11.5, 1.2)
    para(tf, title, 34, TEXT, bold=True, first=True)
    if subtitle:
        para(tf, subtitle, 15, MUTED)
    n_rows, n_cols = len(rows) + 1, len(headers)
    tbl_shape = s.shapes.add_table(n_rows, n_cols, Inches(0.9), Inches(1.8),
                                   Inches(11.5), Inches(0.5 * n_rows))
    tbl = tbl_shape.table
    for c, h in enumerate(headers):
        cell = tbl.cell(0, c)
        cell.text = h
        for p in cell.text_frame.paragraphs:
            for r in p.runs:
                r.font.size = Pt(15)
                r.font.bold = True
                r.font.color.rgb = BG
        cell.fill.solid()
        cell.fill.fore_color.rgb = ACCENT
    for ri, row in enumerate(rows, start=1):
        for c, v in enumerate(row):
            cell = tbl.cell(ri, c)
            cell.text = v
            for p in cell.text_frame.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(13)
                    r.font.color.rgb = TEXT
            cell.fill.solid()
            cell.fill.fore_color.rgb = CARD if ri % 2 else RGBColor(0x16, 0x21, 0x33)
    return s


# ---------------------------------------------------------------- slides

title_slide(
    "RegIntel AI",
    "Enterprise Knowledge & Operations Assistant",
    "IIT Patna GenAI Development Program · Final Evaluation · Project 3 — "
    "Agentic AI Assistant",
)

content_slide("The problem", [
    ("Fragmented knowledge",
     ["Policies, SOPs, and answers live in scattered documents — "
      "employees can't find them."]),
    ("Slow, inconsistent support",
     ["Ticket queues grow while answers already exist in the knowledge base."]),
    ("Unsupported chatbot answers",
     ["Generic assistants guess — no evidence, no citations, no trust."]),
    ("Weak auditability & access control",
     ["Who saw what, which document backed an answer, what action was "
      "taken — untracked."]),
    ("Uncontrolled model cost",
     ["No visibility into tokens, latency, or spend per department."]),
])

content_slide("The solution", [
    ("One agentic assistant for employees",
     ["Ask → evidence-grounded answer with citations → or a governed "
      "action (ticket, CRM case)."]),
    ("LangGraph-orchestrated",
     ["13-node graph with conditional routing, multi-turn state, and "
      "per-node status streaming."]),
    ("Configuration-driven",
     ["Departments, tools, guardrails, and models are YAML — Finance "
      "onboarded with zero new code."]),
    ("Enterprise-ready seams",
     ["Auth, CRM, search, LLM, and speech are adapter interfaces — swap "
      "stubs for Entra/Bedrock/Genesys by config."]),
])

mono_slide("Architecture", """\
  Employee (Angular :4200 / Streamlit :8501 / Genesys agent-assist)
        │  NDJSON stream: status → tokens → citations → usage
        ▼
  FastAPI ── identity (stub │ JWT/JWKS) ── audit_log ── use-case config
        │
        ▼
  LangGraph runner ── initialize → classify → conditional route
        │                              ├── retrieve → generate → guardrail
        │                              ├── ticket_lookup │ crm_lookup
        │                              ├── clarify → confirm → ticket_create │ crm_case_create
        │                              └── direct / error_handler
        ▼
  Tools (server-side allowlist) ── knowledge_search · ticket_lookup
        │                            ticket_create · crm_lookup · crm_case_create
        ▼
  Hybrid retriever (BM25 + vector → RRF → reranker, ACL-filtered)
  SQLite store · ingestion pipeline · audit · analytics""",
    note="Every node emits a status event — the UI shows the live node "
         "trace; the eval runner asserts on it.",
)

mono_slide("LangGraph workflow — state, routing, tools", """\
  user message
      │
      ▼
  initialize ──▶ classify ──▶ route on intent
      │                        ├─ knowledge_query → build_filters → retrieve
      │                        │      → generate (cited) → guardrail → respond
      │                        ├─ ticket_lookup / crm_lookup → tool → respond
      │                        ├─ ticket_create / crm_case_create
      │                        │      → clarify (missing fields)
      │                        │      → duplicate_check → confirm_action → write
      │                        ├─ confirm / cancel → resolve pending action
      │                        └─ direct → generate → guardrail → respond
      ▼
  error_handler ◀── any tool failure (graceful, audited)""",
    note="Pending actions persist in the SQLite checkpointer — "
         "'yes'/'no' resolves across turns.",
)

table_slide("Five tools — real function calling",
    ["Tool", "Purpose", "Safety"],
    [
        ["knowledge_search", "Hybrid retrieval over dept-approved corpus",
         "ACL filter + rerank threshold → honest not-found"],
        ["ticket_lookup", "Employee's own support tickets",
         "Owner-scoped, server-side"],
        ["ticket_create", "Open a validated ticket",
         "Validate → dedupe → explicit confirm → idempotent → audit"],
        ["crm_lookup", "CRM case status", "Owner-scoped, audited"],
        ["crm_case_create", "Open a CRM case",
         "Same full safety contract as tickets"],
    ],
    subtitle="Server-side allowlist per use case — a disabled tool can't "
             "be invoked no matter what the user types.",
)

content_slide("Grounded answers — advanced RAG", [
    ("Hybrid retrieval",
     ["BM25 + vector cosine, merged by reciprocal-rank fusion — both "
      "legs ACL-filtered."]),
    ("Reranking",
     ["LocalReranker rescores on phrase/coverage/title; weak evidence → "
      "not-found path, never a guess."]),
    ("FR-16 query rewriting",
     ["Follow-ups ('what about the expiry?') expanded with conversation "
      "context before retrieval."]),
    ("Full citation contract",
     ["document_id, title, section, chunk, excerpt, retrieval + rerank "
      "scores, version, source URL, access decision."]),
    ("Ingestion pipeline",
     ["Markdown → front-matter → contextual chunking → embed → upsert; "
      "checksum drift detection + dead-letter table."]),
])

content_slide("Safety by design", [
    ("Input/output guardrails",
     ["Prompt-injection patterns blocked; Bedrock ApplyGuardrail merges "
      "when configured."]),
    ("No blind actions",
     ["Create flows validate fields, check duplicates, and require an "
      "explicit 'yes' before writing."]),
    ("Idempotent writes",
     ["Same confirmed request never creates two tickets/cases."]),
    ("Access control",
     ["Department ACLs enforced server-side on both retrieval legs; "
      "conversations and exports are owner-scoped."]),
    ("Audit trail",
     ["auth failures, lookups, writes, ingestion, uploads, not-found "
      "events → audit_log."]),
])

content_slide("Beyond the baseline", [
    ("3 departments by config only",
     ["IT · HR · Finance — a YAML + corpus + employee; zero graph "
      "changes (UJ-07)."]),
    ("Voice",
     ["Browser Web Speech mic → same text pipeline; 🔊 read-aloud. "
      "SpeechProvider boundary for Transcribe/Polly."]),
    ("Genesys agent-assist",
     ["POST /v1/integrations/genesys/suggest — utterance → grounded "
      "suggestion + citations, stateless."]),
    ("Analytics",
     ["Usage, feedback, not-found clustering, adoption funnel, "
      "department cost attribution."]),
    ("Self-service + export",
     ["Dept owners upload markdown → ingested and citable; "
      "conversations export to markdown/JSON for audit."]),
])

content_slide("Quality evidence", [
    ("103 automated tests",
     ["Unit + integration + security (forged/expired JWTs, injection, "
      "cross-employee scope)."]),
    ("31-case golden eval suite",
     ["Runs in pytest AND the Eval page; per-case rubric dims + "
      "rubric_means in the summary."]),
    ("Performance",
     ["P95 first token ≈ 65 ms · full answer ≈ 70 ms locally "
      "(NFR targets: 4 s / 12 s) — harness: scripts/load_test.py."]),
    ("CI", ["Ruff + pytest (incl. golden eval) + Angular build on every push."]),
    ("Traceability",
     ["docs/requirements-traceability.md maps every BRD requirement to "
      "code + tests."]),
])

table_slide("Demo — five flows, five prompts",
    ["#", "Prompt (as e001 / IT Support)", "What it proves"],
    [
        ["1", "how do I connect to the VPN",
         "Grounded answer + full-contract citations"],
        ["2", "what is the cafeteria menu",
         "Honest not-found — no hallucination, logged as a gap"],
        ["3", "show my tickets", "Employee-scoped tool call"],
        ["4", "create a ticket — laptop battery drains in an hour → yes",
         "Clarify → confirm → idempotent write → audit"],
        ["5", "check my case CASE-7001",
         "CRM lookup, owner-scoped; e002 gets not-found"],
    ],
    subtitle="Full 11-step walkthrough with expected outputs: docs/demo-script.md",
)

content_slide("Technology stack", [
    ("Orchestration & agent",
     ["LangGraph · LangChain-style tool/context objects · SQLite "
      "checkpointer (multi-turn state)"]),
    ("Backend",
     ["Python · FastAPI · Pydantic · NDJSON streaming · Mangum "
      "(Lambda entry)"]),
    ("Retrieval & ingestion",
     ["BM25 + hashing-vector hybrid → RRF → reranker · checksum "
      "pipeline · ACL filters"]),
    ("Frontend",
     ["Angular 21 (signals, Tailwind) · Streamlit admin/demo · Web "
      "Speech voice I/O"]),
    ("Cloud seams (config-swapped)",
     ["Entra JWT/JWKS · Bedrock Converse + ApplyGuardrail · DynamoDB · "
      "Redis · Genesys · OpenText"]),
])

content_slide("Honest limitations", [
    ("Local model is deterministic",
     ["Answers are extractive (cited verbatim) — Bedrock Claude "
      "generates fluent prose when configured."]),
    ("Enterprise integrations are boundaries",
     ["Entra, AWS, Genesys, OpenText, production CRM need credentials — "
      "every seam fails closed or degrades locally."]),
    ("Rubric scores are heuristic",
     ["Deterministic proxies until an LLM judge is configured."]),
    ("Voice needs a supporting browser",
     ["Chrome/Edge; controls hide gracefully otherwise."]),
])

title_slide(
    "RegIntel AI",
    "Understand → Design → Implement → Test → Explain",
    "Repo: github.com/<org>/regintel-ai · docs/demo-script.md (walkthrough) · "
    "docs/requirements-traceability.md (coverage) · pytest: 103 green",
)

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)
print(f"wrote {OUT} ({len(prs.slides.__iter__.__self__._sldIdLst)} slides)")
