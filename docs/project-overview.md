# Project Overview

## What RegIntel AI is

A **configuration-driven enterprise knowledge and operations assistant**. It authenticates employees, retrieves department-approved knowledge, completes IT support actions through tools, generates grounded answers with citations, and records conversations, feedback, usage and cost metrics.

## Business problem

Employees search across fragmented policy repositories, knowledge bases and ticketing systems. Responses are slow, inconsistent and hard to audit. Generic chatbots risk unsupported answers, weak access control, missing citations and uncontrolled model cost.

## Business need

- One conversational entry point for knowledge discovery and operational requests
- Evidence-grounded answers with expandable citations and access-aware filtering
- Automation of safe support tasks: knowledge search, ticket lookup, ticket creation
- Multiple departments/use cases via **configuration**, not duplicated code
- Measurement of answer quality, feedback, latency, token usage and attributable cost

## Objectives & POC success measures

| Objective | POC success measure |
|---|---|
| Agentic workflow | ≥3 tools execute through LangGraph conditional routing |
| Grounded answers | Every knowledge answer has ≥1 valid citation, or states evidence was not found |
| Retrieval quality | ≥80% top-5 retrieval relevance on approved eval set |
| Answer quality | Avg rubric score ≥4/5 for groundedness, relevance, completeness |
| Operational safety | 100% of ticket creates validate employee, required fields, duplicate status |
| Performance | First streamed token ≤4s; completed answer ≤12s at P95 (standard queries) |
| Reliability | ≥95% successful completion for supported demo scenarios |
| Observability | 100% of requests carry correlation ID, model usage, latency, outcome |
| Configurability | Second department/use case enabled by config + indexed content only |

## Stakeholders

| Role | Primary need |
|---|---|
| Employee | Ask questions, get cited answers, check/create tickets, give feedback |
| Department Owner | Control approved sources, metadata, prompts, tools, access rules |
| Knowledge Manager | Curate content, review failed retrievals, refresh indexes |
| Support Agent | Receive complete, non-duplicate tickets with conversation context |
| Platform Administrator | Configure use cases, models, guardrails, integrations |
| Security / Compliance | Review access, audit events, data handling, dependency risk |
| Product / Analytics | Monitor adoption, quality, cost, unmet needs |
| Evaluator | Run the project locally, verify IIT Project 3 capabilities |

## Target user journeys

| ID | Journey | Expected outcome |
|---|---|---|
| UJ-01 | Employee asks a policy/IT question | Assistant retrieves authorized content, streams cited answer |
| UJ-02 | Follow-up ("What about contractors?") | Context resolves the reference without repeating the topic |
| UJ-03 | Ask for ticket status | Identity validated; only employee-authorized tickets returned |
| UJ-04 | Ask to create a VPN ticket | Missing fields collected, duplicates checked, confirmation required, ticket created |
| UJ-05 | Ask outside available knowledge | "Evidence not found" stated; escalation path offered |
| UJ-06 | Change language or use voice | Input normalized; response in selected language with citations |
| UJ-07 | Admin enables another use case | Config + approved content activate it, no code duplication |
| UJ-08 | Analyst reviews performance | Dashboard shows usage, feedback, latency, retrieval quality, cost |

## Scope

**In scope (POC):** Entra ID sign-in/JWT; DynamoDB USECASE/CONVERSE config; Graph + OpenText ingestion; contextual chunking; Titan/Cohere embeddings; OpenSearch hybrid retrieval + Cohere rerank; LangGraph orchestration; Claude Sonnet generation + Haiku enrichment + Bedrock guardrails; multi-turn, citations, feedback, streaming, multilingual, optional voice; Angular 21 + Streamlit UIs; metrics/cost/rubric analytics; GitHub + Nexus IQ + JFrog pipeline.

**Out of scope (initial POC):** autonomous high-risk transactions without confirmation; production migration of all repositories; modifying source documents; full CRM write-back, telephony rollout, org-wide deployment; regulatory/legal advice.
