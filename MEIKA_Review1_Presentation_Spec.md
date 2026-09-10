# MEIKA — Phase-I Review 1 Presentation
## Complete Content Specification

**Project:** MEIKA — Explainable AI-Based Personal Financial Copilot for Predictive Budgeting, Goal Forecasting, and Financial Risk Analysis
**Team:** Doron Linton Prince (23CU0330010) · Kannapiran R (23CU0330020) · Baskar Adithiya S (23CU0330006)
**Guide:** Dr. John Aravindhar · Dept. of CSE (AI & ML), 7th Semester
**Institution:** Hindustan Institute of Technology and Science
**Milestone:** Phase-I Review 1 · 14 August 2026

---

## HOW TO USE THIS DOCUMENT

This is a *content specification*, not a deck. For each of the 27 slides it gives: purpose, the exact text to place on the slide, the recommended visual, speaker notes, and the references that back the claims. Slide text is written to be **read from a projector** — short lines, no paragraphs. The depth lives in the speaker notes.

Three things to know before you build from it:

1. **Everything about MEIKA here is traceable** to the Review-1 deck, the project proposal, or the actual source code. Nothing is invented.
2. **No reference paper's result is ever presented as MEIKA's.** Where another study's number appears, it is explicitly attributed.
3. **Statuses are frozen at the 14 August Review-1 state**, exactly as briefed — see the note immediately below, which matters.

---

## ⚠ IMPORTANT — A STATUS DISCREPANCY YOU SHOULD KNOW ABOUT

The brief instructs that Copilot WebSocket, Copilot chat UI, JWT authentication, rate limiting, and Price-Finder catalog seeding be preserved as **PLANNED / TO DO**, and not silently changed.

**That instruction is followed exactly throughout this specification.**

However, you should know *why* it is correct here, because a panel member may probe it. Those items are marked TO DO because that was their state **at the Review-1 milestone on 14 August 2026**. The repository has since moved on — as of the current codebase, Phases 4, 7 and 8 have landed (copilot WebSocket, chat UI, JWT auth, rate limiting), and Price-Finder is live. A Review-1 presentation documents the Review-1 state, so presenting them as TO DO is *accurate for this milestone*, not stale.

To keep you safe either way, **Backup Slide B1** ("Progress Since Review 1") is supplied at the end. It is not part of the 27-slide sequence. Hold it in reserve and show it only if the panel asks what has changed since the review date. This gives you the literal Review-1 board as briefed, plus an honest answer if challenged.

---

# PART A — SOURCE ANALYSIS

## A.1 What MEIKA actually is (verified)

| Dimension | Verified position |
|---|---|
| **Implemented & demonstrated** | Expense capture; REST modules (health, expenses, dashboard); Pydantic validation; PostgreSQL persistence via async SQLAlchemy; spending velocity; month-end projection; category concentration; deterministic Financial Clarity Score; named `XAIFactor` explanations; Flutter dashboard + budget screens; 7 seeded transactions / 6 categories; 2 Alembic migrations; 9 of 11 automated tests passing |
| **Partially implemented** | Core backend logic; budgeting/dashboard UI; Price-Finder module |
| **Planned at Review 1** | Gemini copilot WebSocket; copilot chat UI; goal forecasting; JWT auth; rate limiting; Price-Finder catalog seeding |
| **Research contribution** | Making financial prediction and risk analysis **explainable by construction** — not adding another prediction feature |
| **Explicitly NOT claimed** | No trained ML model; no accuracy/precision/recall/F1/RMSE figures; no large dataset; no user study; no deployment |

## A.2 The central research position

MEIKA is **not** "another AI expense tracker." Its position is:

> An explainability-first personal financial copilot that pairs predictive financial analysis with auditable, factor-level reasoning, so a user can see *why* a financial risk or prediction was produced.

The narrative spine — use this progression repeatedly through the deck:

| Layer | Question answered | MEIKA status |
|---|---|---|
| Tracking | *What happened?* | Implemented |
| Prediction | *What is likely to happen?* | Implemented (velocity, projection) |
| Risk analysis | *What could go wrong?* | Implemented (Clarity Score) |
| Explainability | *Why does the system believe that?* | Implemented (`XAIFactor`) — **the contribution** |
| Copilot | *What should I consider next?* | Planned (bounded) |

## A.3 Literature-to-MEIKA mapping

Ten sources. Method, contribution, limitation, and the MEIKA response for each. Reported figures belong to the cited study and are marked as such.

| # | Author, Year | Method / Technology | Key finding (theirs) | Limitation / gap | MEIKA response |
|---|---|---|---|---|---|
| 1 | Pathak, 2010 *(base paper)* | Survey; four-component DSS framework (data, models, interfaces, user customization) | Formalises a DSS structure reusable outside e-commerce | Pre-dates AI/LLM era; no explainability treatment | Supplies the architectural skeleton: data layer, computation layer, interface layer, per-user customization |
| 2 | Kakulapati et al., 2026 | Django backend, linear regression, NLP, React UI | Effective short-horizon expense prediction and anomaly identification | Reasoning not exposed to the user; no goal forecasting or structured risk analysis | Every predictive output ships with its named factors |
| 3 | Nie et al., 2024 (arXiv:2406.11903) | Survey of LLMs across financial tasks | LLMs improve financial reasoning and real-time decision support | Interpretability, privacy, bias, legal responsibility flagged as the pressing open challenges | Justifies **bounding** the LLM to rephrasing computed values rather than originating them |
| 4 | Deepthi C G et al., 2026 | XGBoost/RF + ARIMA/LSTM + LLM chat + SHAP, serverless microservices | *Their* reported fraud-detection accuracy: 98% | Explainability applied post-hoc to selected models, not structural | Explainability enforced at the type level — a score cannot be returned without its factors |
| 5 | Ganta et al., 2025 | Fraud detection + learning-to-rank recommender + document-grounded chatbot | Frames *fragmentation* as the core fintech weakness | Data sensitivity, explainability, modular scalability under-addressed | One tenant-isolated schema spanning expense, budget, price comparison, conversation |
| 6 | Khan, Li & Cao, 2025 | Survey; accuracy/cost/privacy framework | Identifies privacy, bias, explainability as deployment obstacles | Conceptual; no implementation | Supports the trust argument; motivates deterministic scoring |
| 7 | Badiger et al., 2026 (SSRN 6615358) | Next.js, Prisma, Supabase + Gemini categorization | *Their* reported figures: >91% categorization accuracy, ~78% less manual logging | Limited explainability, single-source data, cold-start, LLM hallucination risk | Grounded generation: the model never originates a financial figure |
| 8 | Unde S. P. et al., 2026 | Banking-API ingestion, CNN/OCR, BERT/LSTM, autoencoders, LLM advisory | Unified real-time dashboard integrating four AI subsystems | Complex multi-model pipeline; final recommendation still opaque | Simpler deterministic core whose every output is traceable |
| 9 | Saini et al., 2025 | Review of ML/NLP/predictive analytics and robo-advisors | Trust rises as financial AI moves "from black-boxed to transparent and explanative" | Review only; no prototype | Directly validates the trust gap MEIKA targets |
| 10 | Patil et al., 2026 | K-Means + Random Forest + nudge theory | *Their* reported figures: 91% / 88% for health scoring and segmentation | No explainability treatment; forecasting and bank integration left as future work | Closest to the goal-forecasting objective; MEIKA holds goal forecasting to the same explainability standard |

**Project-internal sources (not independent external validation):** the Project Proposal (Discussion Draft) and the earlier "Explainable AI Financial Copilot" deck are MEIKA's own material. Use them for consistency of motivation, objectives and scope — never cite them as third-party evidence. The two copies of the copilot deck are the same work; count once.

**Reference-method classification** — state this if asked why MEIKA does not use these:

| Technique | Role in literature | MEIKA status |
|---|---|---|
| Random Forest, XGBoost | Reference method | Not implemented |
| LSTM, ARIMA | Forecasting literature | Possible future work |
| BERT, CNN/OCR | Transaction NLP / receipts | Reference only |
| Isolation Forest, autoencoders | Anomaly detection | Reference only |
| SHAP | Post-hoc XAI | Reference; MEIKA uses factor-based XAI instead |
| LLM (Gemini) | Conversational reasoning | Planned, bounded |
| RAG | Grounded generation | Future scope |

## A.4 Research gap matrix

Legend: ✓ addressed · △ partial · ✗ absent

| Existing work | Prediction | Risk analysis | Conversational AI | Factor-level XAI | Unified system |
|---|---|---|---|---|---|
| Kakulapati et al. | ✓ | ✗ | ✗ | ✗ | ✗ |
| Deepthi C G et al. | ✓ | ✓ | ✓ | △ (SHAP, selective) | ✓ |
| Ganta et al. | ✓ | ✓ | ✓ | ✗ | ✓ |
| Badiger et al. | ✓ | △ | ✓ | ✗ | ✓ |
| Unde S. P. et al. | ✓ | ✓ | ✓ | ✗ | ✓ |
| Patil et al. | △ | ✓ | ✗ | ✗ | △ |
| Nie / Khan (surveys) | — | — | — | flagged as open | — |
| **MEIKA** | **✓** | **✓** | **planned, bounded** | **✓ core design** | **✓** |

**The defensible gap statement:** capable systems exist for prediction, risk and conversation, but factor-level transparency is consistently the weakest column — treated as an add-on where present at all. MEIKA *addresses* this by making it a construction-time constraint.

Phrase it as "addresses / extends / integrates / provides a user-facing implementation of." Never "first ever" or "completely novel."

---
# PART B — SLIDE-BY-SLIDE CONTENT (OUTPUT A)

> **Convention:** "Slide text" is what goes on the slide, verbatim. Keep it. "Speaker notes" is what you say — it is deliberately deeper than the slide.

---

## SLIDE 1 — TITLE

**Purpose:** Establish identity and credibility in five seconds. Nothing else.

**Slide text**
> **MEIKA**
> Explainable AI-Based Personal Financial Copilot for
> Predictive Budgeting, Goal Forecasting, and Financial Risk Analysis
>
> FINAL YEAR PROJECT · PHASE-I REVIEW 1
>
> Doron Linton Prince (23CU0330010) · Kannapiran R (23CU0330020) · Baskar Adithiya S (23CU0330006)
> Guide: Dr. John Aravindhar
> Department of Computer Science & Engineering (AI & ML), 7th Semester
> Hindustan Institute of Technology and Science
> Academic Year 2026–2027 · 14 August 2026

**Visual:** MEIKA ensō logo, generous whitespace, Zen Garden palette (Washi `#FBFBF7`, Sumi `#2F2F2F`, Matcha `#889A7B`). No stock imagery.

**Speaker notes:** One sentence only — "MEIKA is an explainable AI financial copilot; the emphasis throughout this review is on the word *explainable*." Then move on. Do not read the title aloud.

---

## SLIDE 2 — INTRODUCTION

**Purpose:** Frame personal finance as a continuous decision problem, not a record-keeping problem.

**Slide text**
> **Domain** — FinTech + Explainable AI (XAI)
>
> **Background** — Money management is a daily decision task for students, employees, freelancers and families. Most tools only record what already happened.
>
> **The shift** — AI-driven prediction is now common in finance. Understandable reasoning is not.
>
> **MEIKA** — pairs predictive budgeting and risk analysis with an explainability layer: every prediction ships with the computed factors behind it.
>
> *MEIKA moves from tracking financial activity to explaining financial direction.*

**Visual:** Four clean text blocks. Closing line emphasised on its own.

**Speaker notes:** Digital payments have fragmented spending across cards, wallets and subscriptions, producing more transaction data than users can interpret. Budgeting apps solved *capture*. They did not solve *interpretation*. Land the closing line — it is the thesis of the whole review.

**References:** [5], [8] (fragmentation); [2] (retrospective tracking).

---

## SLIDE 3 — MOTIVATION

**Purpose:** Justify why explainability specifically, with literature backing.

**Slide text**
> **Track → Analyze → Predict → Explain → Assist**
>
> - Prediction without reasoning is advice a user cannot check
> - Financial decisions carry real consequence — unverifiable advice is rarely acted on
> - Survey evidence: user trust rises as financial AI moves from black-boxed to transparent and explanative *(Saini et al., 2025)*
> - LLM surveys independently flag interpretability as a leading open challenge *(Nie et al., 2024; Khan, Li & Cao, 2025)*
>
> **Explainability is the gap between tracking money and understanding money.**

**Visual:** Horizontal five-stage progression, with "Explain" highlighted in Matcha. Two literature callouts beneath.

**Speaker notes:** Motivation is evidence-based, not assumed. Three independent surveys converge on the same conclusion: capability is no longer the binding constraint — trust and interpretability are. That is what makes explainability a *research* target rather than a UI preference.

**References:** [9], [6], [7].

---

## SLIDE 4 — PROBLEM STATEMENT

**Purpose:** Four crisp problems. Keep it visually sparse.

**Slide text**
> **Budgeting apps track the past. They don't explain the future.**
>
> **1 · Limited prediction** — transactions logged, reports generated; where finances are heading is not forecast
> **2 · No transparent reasoning** — where predictions exist, users see an output with no account of how it was produced
> **3 · Weak goal forecasting** — long-term savings and goal attainment largely absent from mainstream trackers
> **4 · Limited risk analysis** — overspending and cash-flow risk surfaced late, rarely before they matter
>
> *Existing systems either couple prediction with a black box, or skip prediction entirely.*

**Visual:** Four quadrant cards, one icon each. Bold headline on top.

**Speaker notes:** Problems 2 and 4 compound: the user is warned late, and cannot evaluate the warning when it comes. This is the specific pairing MEIKA targets.

**References:** [2], [4], [9].

---

## SLIDE 5 — EXISTING SYSTEM

**Purpose:** Describe current practice fairly, separating literature findings from claims about commercial products.

**Slide text**
> **Current approach**
> - Manual or account-synced expense logging
> - Rule-based or basic-ML categorization
> - Retrospective charts and reports
> - Occasional robo-advisory for investment
> - Where AI predictions exist, shown as a bare output
>
> **Limitations reported in the literature**
> - Retrospective only — issues surface after the fact
> - Black-box recommendations reduce trust *(Saini et al., 2025)*
> - Tools handle isolated tasks; no unified real-time view *(Unde et al., 2026)*
> - Goal forecasting and proactive risk analysis largely absent

**Visual:** Two columns — "Current approach" / "Limitations". Cite inline.

**Speaker notes:** Be careful here: the limitations are what the *literature* reports, not our audit of commercial apps. Say "typical" and "many existing systems." A panel member who uses one of these apps should not feel you overclaimed.

**References:** [9], [8], [5].

---

## SLIDE 6 — LITERATURE SURVEY

**Purpose:** Show breadth and one consistent gap. This is a table slide, not a prose slide.

**Slide text** — table, 10 rows, columns: **No. · Author & Year · Method / Technology · Key Finding · Limitation / Gap**

Use the ten rows from Part A.3, compressed to one line per cell. If the table is unreadable at projector size, **split across two slides (6A / 6B, five rows each)** rather than shrinking the font.

**Visual:** Clean bordered table. Highlight the "Limitation / Gap" column — that column is the argument.

**Speaker notes:** Do not read the table. Say: "Ten recent works. Read down the last column and the same gap recurs — the reasoning behind the output is not exposed. Deepthi et al. come closest with SHAP, but apply it to selected models rather than requiring it of every recommendation." Then move on. Reported accuracies in this table belong to those studies — say so out loud if you point at one.

**References:** [1]–[10].

---

## SLIDE 7 — RESEARCH GAP

**Purpose:** The strongest slide in the deck. Make the gap visual and undeniable.

**Slide text** — matrix, legend ✓ addressed / △ partial / ✗ absent

> | Existing work | Prediction | Risk | Conversational | Factor-level XAI | Unified |
> |---|---|---|---|---|---|
> | Kakulapati et al. | ✓ | ✗ | ✗ | ✗ | ✗ |
> | Deepthi C G et al. | ✓ | ✓ | ✓ | △ | ✓ |
> | Ganta et al. | ✓ | ✓ | ✓ | ✗ | ✓ |
> | Badiger et al. | ✓ | △ | ✓ | ✗ | ✓ |
> | Unde S. P. et al. | ✓ | ✓ | ✓ | ✗ | ✓ |
> | Patil et al. | △ | ✓ | ✗ | ✗ | △ |
> | **MEIKA** | **✓** | **✓** | **planned** | **✓ core** | **✓** |
>
> **The Factor-level XAI column is the gap. MEIKA addresses it by construction.**

**Visual:** Matrix with the XAI column shaded so the run of ✗ is immediately visible.

**Speaker notes:** This single column is the research argument. Note honestly that MEIKA's "conversational" cell says *planned* — we are not claiming everything. Claiming the XAI column alone is stronger than claiming all five, because it is defensible. If asked whether we are "first": no — we say MEIKA *addresses* and *provides a user-facing implementation of* factor-level transparency.

**References:** [2], [4], [5], [7], [8], [10].

---

## SLIDE 8 — PROPOSED SOLUTION

**Purpose:** Introduce MEIKA as explainability-first, and name the modules.

**Slide text**
> **MEIKA — an explainability-first personal financial copilot**
>
> | Module | What it does |
> |---|---|
> | Expense management | Capture, validate, persist — tenant-scoped |
> | Predictive budgeting | Spending velocity → month-end projection |
> | Financial Clarity Score | Deterministic risk score from auditable factors |
> | Explainability layer | Named `XAIFactor` objects: label · detail · value |
> | Financial risk analysis | Pace · projection · concentration |
> | Goal forecasting | *Roadmap* |
> | Conversational copilot | *Planned — bounded to computed factors* |
>
> **Design rule: never show a financial score as a bare number.**

**Visual:** Module grid. Roadmap/planned items visually de-emphasised (outline, not filled) so status is readable at a glance.

**Speaker notes:** Point at the two italicised rows deliberately. Volunteering what is *not* built buys credibility for everything you claim *is*.

---

## SLIDE 9 — OBJECTIVES

**Purpose:** Five measurable, demonstrable objectives.

**Slide text**
> **1 · Predictive budgeting engine** — forecast month-end spend from live transaction history and current-month velocity, with alerts before overspending
> **2 · Explainable Clarity Score** — risk score from ≥ 3 auditable factors (pace, projection, concentration); every number traceable to source data
> **3 · Goal forecasting** — project whether a savings/spending goal is on track, updated as expenses are logged
> **4 · Explainable conversational copilot** — ground every reply in computed XAI factors; zero fabricated figures
> **5 · ≥ 20% functional implementation** — 3 live, tested REST modules (health, expenses, dashboard) by Review 1

**Visual:** Five numbered cards. Objective 5 carries a "✓ met" badge.

**Speaker notes:** Each objective states a measurable condition — "≥ 3 factors", "3 REST modules", "zero fabricated figures". Objective 5 is the Review-1 deliverable and it is met; the rest are Phase-II targets.

---

## SLIDE 10 — SYSTEM ARCHITECTURE

**Purpose:** Show a real, layered, implementable architecture.

**Slide text**
> **Flutter client** (Riverpod · Dio) — Sign-in · Dashboard · Budget · Add Expense · Price-Finder · Copilot
> ↓ REST `/api/v1/...`  ·  WebSocket `/ws/...` *(planned)*
> **FastAPI backend** — routers → services; Pydantic validation
> ↓
> **Service layer** — `dashboard_service`: velocity · projection · concentration · Clarity Score
> ↓
> **PostgreSQL 16** — async SQLAlchemy 2.0 · Alembic · tenant-isolated by `user_id`
> ↓
> **Explainability layer** — `XAIFactor` objects
> ↓
> **Financial Clarity Score + risk level** → **Bounded Gemini reasoning layer** *(planned)*

**Visual:** Use the project's architecture diagram. Mark planned components with a dashed border and a "(planned)" tag so implemented and planned are distinguishable at a glance.

**Speaker notes:** Two points worth making. First, computation lives in the service layer, not the routers — routers are thin, so the financial logic is unit-testable in isolation. Second, tenant isolation is structural: `user_id` is on every owned table from the first migration, and every query is scoped through it.

**References:** [1] for the four-component DSS framing.

---

## SLIDE 11 — METHODOLOGY

**Purpose:** The seven-stage pipeline, one line each.

**Slide text**
> **1 Capture** — user logs an expense in the Flutter app; Dio sends it to the REST API
> **2 Validate** — FastAPI checks the payload against a Pydantic schema at the boundary
> **3 Persist** — async SQLAlchemy writes to PostgreSQL, scoped to `user_id`
> **4 Compute** — `dashboard_service` derives velocity, month-end projection, category concentration
> **5 Explain** — each quantity becomes a named `XAIFactor` (label, detail, value)
> **6 Present** — the UI renders the score together with its factors — never a bare number
> **7 Converse** *(planned)* — the copilot reasons only over these computed factors

**Visual:** Vertical or horizontal seven-stage flow. Stage 7 dashed.

**Speaker notes:** Emphasise that stages 4 and 5 happen in the *same* function. The factor and the penalty it explains are built together, so they cannot drift apart. There is no separate explanation-generation step that could describe something other than what was computed — that is the mechanism behind the whole explainability claim.

---

## SLIDE 12 — DATA / INPUT

**Purpose:** Be precise and modest about the data. This is where overclaiming would be easiest and most damaging.

**Slide text**
> **Live operational data — IN USE**
> Source: the application's own Expense API — not a static training dataset
> Records: **7 seeded transactions across 6 categories**, growing with real usage
> Fields: title · category · amount · store · transit cost/mode · date · `user_id`
> Preprocessing: Pydantic validation · category-enum normalization · UTC timestamps · tenant isolation by `user_id`
>
> **Seoul retail catalog — PLANNED**
> Store / Product / ProductListing / PriceQuote — modeled and migrated, not yet seeded
>
> *Prototype operational data — not a large ML training dataset.*

**Visual:** Two panels, "IN USE" and "PLANNED", with a clear status badge on each. Closing caveat in its own bar.

**Speaker notes:** Say the caveat out loud before anyone asks. Seven transactions is enough to prove the pipeline computes and explains correctly; it is not a sample supporting statistical inference. Because the scoring engine is deterministic and not trained, a small dataset limits *calibration evidence* — it does not limit correctness.

---

## SLIDE 13 — FINANCIAL CLARITY SCORE

**Purpose:** The signature visual of the deck.

**Slide text**
> **FINANCIAL CLARITY SCORE**
> # 91 / 100 — LOW RISK
>
> | Pace | Projection | Concentration |
> |---|---|---|
> | 112% of even-pace budget | projected ₩674,488 vs ₩600,000 budget | top category 32% of spend |
>
> Score = 100 − (bounded penalties from each factor)
>
> *Current prototype output — not a validated population-level benchmark.*

**Visual:** Large score dial, three factor cards beneath, each with its real computed sentence. Caveat line in small type at the base.

**Speaker notes:** Walk the panel through one factor end to end: "Spent ₩282,850 against an expected ₩251,613 by day 13 of 31 — that is 112% of even pace, which contributes a bounded pace penalty." Then say the key line: *every one of these numbers comes from the database, and the user sees all of them.* Label the 91 as a prototype output before being asked.

---

## SLIDE 14 — EXPLAINABLE AI

**Purpose:** Show the XAI mechanism and contrast it with black-box practice.

**Slide text**
> **Score → Why? → Factors → Evidence**
>
> **Black-box approach**
> Input → ML model → Score → *"why?"* → hard
>
> **MEIKA approach**
> Input → explicit computation → named factors → Clarity Score → traceable explanation
>
> Each `XAIFactor` carries: **label** (what was detected) · **detail** (the numbers behind it) · **value** (computed magnitude)
>
> **The score and its factors are returned in the same response — a score cannot be shown without its reasoning.**

**Visual:** Two stacked pipelines, black-box greyed out, MEIKA in Matcha. Highlight the closing line.

**Speaker notes:** The structural point: in a post-hoc pipeline the explanation *approximates* the model's reasoning and may be unavailable for some outputs. Here the explanation is a restatement of the computation, because both are produced by the same operation. That property is enforced by the response schema — the Clarity Score object cannot be constructed without a factor list. This is why we call it explainable *by construction* rather than explainable *after the fact*.

**References:** [4] for SHAP as the post-hoc contrast; [9], [6] for why it matters.

---
## SLIDE 15 — PREDICTIVE BUDGETING

**Purpose:** Show real forecasting, and be explicit that it is arithmetic, not a learned model.

**Slide text**
> **Implemented today**
> - **Spending velocity** = spend to date ÷ elapsed days
> - **Month-end projection** = velocity × days in month
> - **Projected overage** = projection − monthly budget (floored at zero)
> - **Pace comparison** against an even spread of the budget
> - Overspending signalled *before* month end
>
> **Guard:** projection is withheld below 7 days of data — too few days and one ordinary purchase distorts it. The system says so instead of guessing.
>
> **Planned:** richer forecasting (periodicity, recurring obligations)
>
> *Current implementation is deterministic arithmetic over live rows — no trained model.*

**Visual:** Two formula cards, then a small timeline showing the 7-day warm-up guard.

**Speaker notes:** The warm-up guard is worth dwelling on — it is a deliberate design decision that *withholds* output rather than showing a confident-looking number from thin data. That is the same honesty principle as the XAI layer, applied to forecasting. If asked why not LSTM/ARIMA: those appear in the literature as forecasting approaches, but implementing one now would add an unexplainable component to a system whose contribution is explainability, and there is not yet enough history to train on.

**References:** [4], [8] for LSTM/ARIMA as reference methods — explicitly not MEIKA's implementation.

---

## SLIDE 16 — GOAL FORECASTING

**Purpose:** Present the roadmap module honestly.

**Slide text**
> **ROADMAP — not yet implemented**
>
> Planned design:
> - User defines a savings or spending goal
> - System tracks current trajectory against it
> - Forecasts on-track / at-risk as new expenses are logged
> - **Held to the same standard:** the forecast must expose its factors, or it is not shown
>
> Literature position: goal planning is either absent from trackers, or delivered without interpretable reasoning *(Patil et al., 2026 — forecasting and bank integration left as future work)*

**Visual:** Clear "ROADMAP" banner. Wireframe sketch only — **do not mock a screenshot of a feature that does not exist.**

**Speaker notes:** State plainly that no goal model, service or endpoint exists in the codebase today. What we *have* decided is the constraint it will be built under. Patil et al. is the closest work and it defers exactly this — which is what makes it a defensible Phase-II target rather than a gap we overlooked.

**References:** [10].

---

## SLIDE 17 — CONVERSATIONAL COPILOT

**Purpose:** Explain the bounded architecture and why bounding is the point.

**Slide text**
> **PLANNED — bounded by design**
>
> User question
> ↓
> **Computed financial factors** (from the deterministic layer)
> ↓
> Context assembly
> ↓
> Gemini reasoning
> ↓
> Grounded explanation
>
> **The copilot may rephrase computed values. It may not originate them.**
> It cannot invent balances, spending figures, predictions, risk factors or transactions — the backend remains the sole source of numerical truth.

**Visual:** Vertical flow, with a bounding box drawn around the Gemini stage and a caption "may rephrase, may not originate."

**Speaker notes:** This is a hallucination-control argument. LLM surveys identify interpretability and reliability as leading deployment obstacles, so we constrain the model's authority rather than trusting its output. A fallback path constructs a reply directly from the computed factors when the model is unavailable, so the feature degrades to something correct rather than something wrong.

**References:** [6], [7] for LLM limitations; [3] for hallucination risk in a finance LLM deployment.

---

## SLIDE 18 — CURRENT IMPLEMENTATION / DEMONSTRATION

**Purpose:** The evidence slide. Concrete, countable, verifiable.

**Slide text**
> **First module — 20% of project work**
>
> **3** live REST endpoints — health · expenses · dashboard
> **2** Alembic migrations applied to a real Postgres schema
> **9 / 11** automated tests passing (pytest)
> **3** live XAI factors — pace · projection · concentration
>
> | Component | Status |
> |---|---|
> | Project scaffold | DONE |
> | DB schema, models, migrations | DONE |
> | Core backend logic (velocity, Clarity Score / Price-Finder) | PARTIAL |
> | XAI Copilot WebSocket integration | TO DO |
> | Frontend design system | DONE |
> | Dashboard & budgeting UI / Price-Finder screen | PARTIAL |
> | Copilot chat UI | TO DO |
> | Security, JWT auth, rate limiting | TO DO |
>
> *Next: seed the Price-Finder catalog, wire the Gemini copilot, replace the interim auth header with JWT.*

**Visual:** Four large stat tiles across the top, status board beneath. Colour-code DONE / PARTIAL / TO DO consistently.

**Speaker notes:** These are Review-1 figures as of 14 August. Do not inflate them. The 9/11 is worth addressing directly rather than hiding: the two failures correspond to modules still under construction at that date. A panel respects a team that reports a failing test honestly far more than one claiming 11/11.

> **If asked "what has changed since?"** — this board is the state at the review date. Switch to Backup Slide B1.

---

## SLIDE 19 — LIVE RESULT / CURRENT OUTPUT

**Purpose:** Show the working system on real computed data.

**Slide text**
> **Live application — real computed data**
>
> **Financial Clarity Score: 91 / 100 — Low risk**
> **Cash-flow outlook: budget lasts to Aug 27 at current pace**
>
> Produced from: 7 transactions · 6 categories · day 13 of 31 · ₩600,000 monthly budget
> Factors shown to the user: pace (112% of even pace) · projection (₩674,488 vs ₩600,000) · concentration (top category 32%)
>
> *Current prototype output. Not a validated financial risk benchmark.*

**Visual:** The two real app screenshots (Dashboard + Budget). Label them "Prototype interface."

**Speaker notes:** Explain what produced the runway date: remaining budget ÷ current daily velocity, giving roughly 14 days from 13 August. It is a linear extrapolation and inherits that limitation — say so. Everything on this slide is computed from database rows, none of it is hard-coded or mocked.

> **Pre-empt this:** the screenshots show a **Copilot tab** in the navigation bar, while Slide 17 lists the copilot as *planned*. Say it before the panel spots it — "the navigation shell is in place; the copilot screen behind it is the Phase-4/7 work still to come." Leaving the mismatch unaddressed looks like an overclaim; naming it takes five seconds.

---

## SLIDE 20 — COMPARISON WITH EXISTING SYSTEMS

**Purpose:** Position without overclaiming.

**Slide text**
> | Feature | Traditional tracker | Typical AI finance app | MEIKA |
> |---|---|---|---|
> | Expense tracking | ✓ | ✓ | ✓ |
> | Prediction | limited | ✓ | ✓ |
> | Risk analysis | limited | ✓ | ✓ (factor-based) |
> | Goal forecasting | limited | limited | planned |
> | Explainability | ✗ | often limited | **core design** |
> | Factor-level reasoning | ✗ | rare | ✓ |
> | Conversational copilot | limited | ✓ | planned, bounded |
> | Unified architecture | partial | varies | ✓ |
> | Requires model training | ✗ | ✓ | ✗ |

**Visual:** Comparison table, MEIKA column emphasised.

**Speaker notes:** Use "typical" and "many existing systems" — this characterises classes of system from the literature, not every product on the market. Note the last row honestly: no training is a *trade*. We give up pattern discovery to gain reproducibility and auditability.

---

## SLIDE 21 — RESEARCH CONTRIBUTION

**Purpose:** State the contribution precisely and no larger than it is.

**Slide text**
> 1. **Explainability-first financial risk scoring** — a deterministic Clarity Score whose every component is named and auditable
> 2. **Factor-level reasoning as a structural constraint** — `XAIFactor` carried in the same response as the score
> 3. **Predictive analysis integrated with transparency** — velocity and projection computed from live data, each explained
> 4. **Unified decision-support architecture** — one tenant-isolated schema across tracking, budgeting and analysis
> 5. **Grounded conversational design** *(planned)* — the model rephrases computed values, never originates them
> 6. **Working prototype** — 3 tested REST modules producing real explained output
>
> *The contribution is not "AI applied to personal finance." It is making financial prediction and risk analysis explainable by construction.*

**Visual:** Six numbered contribution cards; closing line emphasised.

**Speaker notes:** If you say only one thing in the review, say the closing line. Everything else supports it.

---

## SLIDE 22 — ADVANTAGES

**Slide text**
> - **Transparent scoring** — no bare numbers; reasoning always attached
> - **Reproducible** — deterministic; identical inputs always yield an identical, inspectable score
> - **Auditable** — any score can be recomputed by hand from the factors shown
> - **Proactive** — risk surfaced before month end, not after
> - **Modular** — thin routers, testable service layer
> - **Cross-platform client** — single Flutter codebase
> - **No GPU, no training pipeline** — runs on a standard laptop plus Postgres
> - **Clean separation** — computation and language generation are distinct layers

**Visual:** Two columns of four.

**Speaker notes:** "Auditable" is the one to stress — a user, a reviewer, or an examiner can take the three factors on screen and reproduce the 91 with a calculator. Very few AI systems permit that.

---

## SLIDE 23 — LIMITATIONS

**Purpose:** Credibility. Do not soften these.

**Slide text**
> - Prototype dataset is small — 7 transactions, 6 categories
> - Limited transaction history; cold-start for new users not yet addressed
> - Scoring weights are design choices, **not empirically calibrated**
> - Projection is linear — no periodicity or recurring-obligation modelling
> - Goal forecasting not yet implemented
> - Gemini copilot integration still planned
> - No bank / Open Banking integration
> - Security hardening in progress (JWT, rate limiting pending)
> - No user study conducted — explainability is structurally guaranteed, not yet shown to *help* users
> - The Clarity Score is a prototype indicator, not a certified financial risk measure

**Visual:** Plain list. Do not decorate. A clean, unembellished limitations slide reads as confidence.

**Speaker notes:** Lead with the user-study gap if you have time for only one — it is the most intellectually honest point in the deck. We can prove the explanation faithfully describes the computation; we have *not* shown that users find it useful. That is Phase-II work and naming it pre-empts the panel's sharpest question.

---

## SLIDE 24 — FUTURE SCOPE

**Slide text**
> **Near term** — goal forecasting · Gemini copilot integration · JWT auth & rate limiting · Price-Finder catalog
> **Data & integration** — Open Banking / Account Aggregator · receipt OCR · multimodal input
> **Modelling** — advanced time-series forecasting · empirical calibration of the Clarity Score · bounded learned components that still emit named factors
> **Interaction** — voice assistant · RAG-grounded financial knowledge
> **Privacy & scale** — federated learning · privacy-preserving analytics · DPDP Act alignment
> **Product** — shared/family budgets · investment tracking · credit-score analysis
>
> *Future scope — distinct from current implementation.*

**Visual:** Grouped columns by theme. Keep the closing caveat visible.

**Speaker notes:** If asked which is next: goal forecasting, because it is a stated objective and the only one of the five not yet started. Note that even future learned components are constrained to emit named factors — the explainability rule extends rather than relaxes.

**References:** [8] (OCR, real-time integration), [3] (production architecture), [6], [7] (privacy).

---

## SLIDE 25 — PROJECT ROADMAP

**Slide text**
> **Phase 1 — Literature survey + base architecture** — DONE
> **Phase 2 — Data model, schema, migrations** — DONE
> **Phase 3 — Core backend logic: velocity, Clarity Score, Price-Finder** — PARTIAL
> **Phase 4 — XAI Copilot WebSocket integration** — TO DO
> **Phase 5 — Frontend design system** — DONE
> **Phase 6 — Dashboard & budgeting UI** — PARTIAL
> **Phase 7 — Copilot chat UI** — TO DO
> **Phase 8 — Security, JWT auth, rate limiting** — TO DO
>
> **Review 1 = Phases 1, 2, 5 complete; 3 and 6 in progress**

**Visual:** Horizontal timeline with status chips. Mark the Review-1 line clearly.

**Speaker notes:** This is the same status board as Slide 18, arranged chronologically. Consistency between the two matters — a panel will check.

---

## SLIDE 26 — CONCLUSION

**Slide text**
> **MEIKA moves personal finance from retrospective tracking toward predictive, explainable decision support.**
>
> - **Prediction** — spending velocity and month-end projection from live data
> - **Risk analysis** — a deterministic Financial Clarity Score
> - **Explainability** — named `XAIFactor` objects, inseparable from the score
> - **Architecture** — Flutter · FastAPI · PostgreSQL, tenant-isolated
> - **Demonstrated** — 3 tested REST modules producing real explained output
>
> **Next:** goal forecasting and a bounded conversational copilot, held to the same explainability standard.

**Visual:** Five summary points, forward-looking line at the base.

**Speaker notes:** Close on the standard, not the feature list: the rule that no figure reaches the user without its justification is what carries into Phase II.

---

## SLIDE 27 — REFERENCES

**Slide text** — IEEE numbered list, see Part C.

**Visual:** Two columns, small type. Do not read aloud.

---

## BACKUP SLIDE B1 — PROGRESS SINCE REVIEW 1
*(Not part of the 27-slide sequence. Show only if the panel asks what has changed since 14 August 2026.)*

**Slide text**
> **Status board — Review 1 (14 Aug) vs. current repository**
>
> | Module | At Review 1 | Current |
> |---|---|---|
> | Copilot WebSocket | TO DO | Implemented |
> | Copilot chat UI | TO DO | Implemented |
> | JWT auth + rate limiting | TO DO | Implemented (MVP baseline) |
> | Price-Finder engine | PARTIAL | Implemented (live search) |
> | Dashboard & budget UI | PARTIAL | Implemented |
> | Live Gemini call path | TO DO | Implemented, **not yet validated** |
> | Goal forecasting | TO DO | **Still not started** |
>
> *Figures on Slide 18 are the verified Review-1 state. This is the position since.*

**Speaker notes:** Use this only if asked. Two honesty points: the live Gemini call path is written and defensively wrapped but has never been run against a real API key, so it is *not* validated; and goal forecasting remains genuinely unstarted. Do not let the progress narrative blur either.

---
# PART C — EXPECTED PANEL QUESTIONS & ANSWERS

Twenty-five likely Review-1 questions with technically defensible answers. Answers are grounded in the project material and the supplied literature.

**1. How is MEIKA different from an expense tracker?**
A tracker answers "what happened." MEIKA adds three layers on top: what is likely to happen (velocity, month-end projection), what could go wrong (Clarity Score), and — the contribution — why the system believes it (named `XAIFactor` objects). A tracker shows you a chart of the past; MEIKA shows you a projection and the reasoning behind it.

**2. Why is explainability necessary in personal finance?**
Because the user is expected to act on the advice, with real financial consequence. Saini et al. (2025) find trust rises as financial AI moves from black-boxed toward transparent and explanative operation; Nie et al. (2024) and Khan, Li & Cao (2025) independently identify interpretability as a leading open challenge for financial LLMs. Advice a user cannot verify is advice they will not act on.

**3. Why deterministic XAI instead of SHAP?**
SHAP explains a trained model *after the fact* — it approximates the model's reasoning and can be omitted for some outputs. MEIKA has no trained model to approximate: the penalty and the factor describing it are produced in the same operation from the same quantities, so the explanation is a restatement of the computation rather than an estimate of it. Deepthi et al. (2026) use SHAP, but apply it selectively; we wanted the guarantee to hold for every output.

**4. Is MEIKA using machine learning right now?**
No, and that is deliberate for this phase. The Clarity Score is a deterministic penalty function over three named quantities. There is no training corpus, no learned weights and no inference step. The trade is explicit: we give up pattern discovery in exchange for outputs that are reproducible and auditable.

**5. Why not use XGBoost or LSTM immediately?**
Three reasons. There is not yet enough transaction history to train on. Adding a learned component now would introduce an unexplainable element into a system whose contribution is explainability. And those models appear in the literature (Deepthi et al., Unde et al.) as *reference* methods — adopting them because a paper used them would not be a design decision. When learned components are added, they will be required to emit named factors like everything else.

**6. What is the Financial Clarity Score?**
A bounded integer from 0–100 with a categorical risk level, expressing current financial risk posture. It starts at 100 and subtracts bounded penalties contributed by three factors. Low risk is ≥ 70, moderate 40–69, high below 40.

**7. How are its factors calculated?**
Let *S* = spend to date, *d* = elapsed days, *D* = days in month, *B* = monthly budget.
- **Pace:** expected-to-date *E* = *B·d/D*; ratio *r* = *S/E*; penalty scales with *r* − 1, capped at 35.
- **Projection:** velocity *v* = *S/d*; projection *P* = *v·D*; overage *O* = max(0, *P* − *B*); penalty scales with *O/B*, capped at 40.
- **Concentration:** *c* = largest category ÷ total; penalised only above a 40% tolerance, capped at 15.
Score = 100 − sum of penalties.

**8. Why were pace, projection and concentration chosen?**
They cover three distinct failure modes with no overlap: spending too fast *right now* (pace), heading for an overspend *by month end* (projection), and fragility from over-reliance on one category (concentration). Each is independently observable from the transaction table, which is what makes each independently explainable. A factor that could not be traced to a named quantity would break the design rule.

**9. Can you demonstrate that the score is really traceable?**
Yes — recompute it live. At day 13 of 31, ₩282,850 spent against a ₩600,000 budget: expected-to-date is ₩251,613, so pace ratio is 1.124 → penalty ≈ 4.34. Velocity ₩21,758/day → projection ₩674,488 → overage ₩74,488 → penalty ≈ 4.97. Top category is 32%, below the 40% tolerance → penalty 0. Total ≈ 9.31, so the score is 100 − 9.31 ≈ **91**. That matches the displayed score exactly, and every input is visible to the user.

**10. What is the current dataset, and why is it small?**
Seven seeded transactions across six categories, from the application's own Expense API — live operational data, not a training corpus. It is small because it is a Phase-I functional prototype. Critically, dataset size limits *calibration evidence*, not correctness: because the engine is deterministic and untrained, a small dataset does not degrade the score's validity, it only limits what we can claim about the weights.

**11. Why is 9/11 tests passing acceptable?**
The two failures correspond to modules still under construction at the review date. We report the real number rather than excluding failing tests to present 11/11. The tests that pass cover the demonstrated path: health, expenses, dashboard, and the scoring logic.

**12. How will goal forecasting work?**
The user defines a savings or spending target; the system tracks the current trajectory and forecasts on-track or at-risk as new expenses land. It is not implemented — no goal model, service or endpoint exists today. The design commitment already made is that a goal projection must expose its factors or it will not be displayed.

**13. How will forecasting accuracy be evaluated?**
Once sufficient history exists: MAE, RMSE and MAPE of projected versus realised month-end spend. We are not reporting those figures now because the experiment has not been run — reporting them would be fabrication.

**14. What is the role of the LLM?**
Narrow and bounded. It rephrases already-computed figures conversationally. It is not a source of financial values and cannot introduce a number the deterministic layer did not produce. If it is unavailable, a fallback reply is constructed directly from the computed factors.

**15. How do you prevent hallucinations?**
By removing the model's authority to originate figures. The reply is grounded in the computed factor set, the model is constrained by prompt construction, and a deterministic path produces a correct reply when the model is absent. Badiger et al. (2026) flag LLM hallucination as a live limitation of their platform — bounding the model's role is our structural response.

**16. How do you protect user financial data?**
Tenant isolation is structural: every user-owned table carries `user_id` from the first migration, and every query against owned data is scoped through it. JWT authentication and rate limiting are planned for Phase 8. We are explicitly not claiming a completed security posture at Review 1.

**17. How does `user_id` provide tenant isolation?**
It is a column on every owned table plus a mandatory filter on every query in the service layer. The identifier is derived from the authenticated session rather than accepted from the request body, so a caller cannot reach another tenant's rows by altering a parameter.

**18. What happens for a new user with no history?**
This is the cold-start case and it is handled explicitly rather than silently. Below seven days of data the projection is withheld and replaced by a factor stating why. A warm-up coefficient also damps the pace and concentration penalties proportionally, so one ordinary purchase early in a month does not produce an alarming score.

**19. Why does the score never seem to go very low?**
Good observation. The three penalties cap at 35, 40 and 15, so they sum to at most 90 — the attainable range is effectively 10–100 rather than 0–100. The lower clamp is defensive. This is a known property of the current weights and a target for calibration.

**20. What is the research gap, in one sentence?**
Existing systems achieve prediction, risk analysis and conversation, but factor-level transparency is consistently treated as an add-on or omitted — MEIKA addresses that by making it a construction-time constraint.

**21. What is the actual contribution?**
Not "AI applied to personal finance." It is that a financial decision-support system can be built so that no figure reaches the user without its justification, demonstrated in a working prototype.

**22. Aren't you just doing arithmetic and calling it AI?**
Fair challenge. The contribution is not model sophistication — it is the architecture of explanation. The system sits in Explainable AI and decision-support systems, following the four-component DSS framework of the base paper (Pathak, 2010). Deliberately choosing a transparent computation over an opaque model, and enforcing that choice structurally, is the research position, not a shortcut.

**23. What are the limitations?**
Small prototype dataset; uncalibrated scoring weights; linear projection with no periodicity modelling; goal forecasting unimplemented; copilot planned; no bank integration; security hardening incomplete; and no user study — we can show the explanation faithfully describes the computation, not yet that users find it useful.

**24. How will the project scale?**
Architecturally it already separates concerns: thin routers, a testable service layer, async database access, and a schema tenant-isolated from the first migration. Scaling work identified includes moving rate limiting to a shared store for multi-worker deployment and adding indexes as transaction volume grows.

**25. What if the copilot gives incorrect advice, and how will recommendations be validated?**
The copilot cannot originate figures, so a numerical error would have to originate in the deterministic layer — which is reproducible and unit-testable. Phrasing is constrained by grounding and the fallback path. For validation, the Clarity Score needs calibration against realised outcomes across a diverse user sample before it should be treated as a measure rather than an indicator; that is stated as a limitation, not glossed over.

---

# PART D — IEEE REFERENCE LIST

Use these on Slide 27. Verify each against the original PDF before final submission.

[1] B. Pathak, "A Survey of the Comparison Shopping Agent-Based Decision Support Systems," *Journal of Electronic Commerce Research*, vol. 11, no. 3, pp. 178–192, 2010. *(Base paper.)*

[2] V. Kakulapati, D. Sumanth, M. Harshitha Reddy, and P. Saisharath, "AI-Powered Personal Expense Tracker," *Grenze International Journal of Engineering and Technology*, Grenze ID: 01.GIJET.12.1.401_1, 2026.

[3] R. Badiger et al., "Next.js-Powered AI Platform for Smart Expense Tracking, Budgeting and Insights," SSRN 6615358, 2026.

[4] Deepthi C. G. et al., "AI-Powered Finance Management Platform," in *Proc. IEEE Int. Conf. on Sustainable Financial Technologies (ICSFT)*, 2026.

[5] P. Ganta, G. Agarwal, R. Jha, and K. Nagaraj, "An Intelligent Multi-Module Financial Assistant for Personalized Budgeting, Risk Alerts, and Adaptive Investment Advisory," in *Proc. 2025 9th Int. Conf. on Computational System and Information Technology for Sustainable Solutions (CSITSS)*, 2025, doi: 10.1109/CSITSS67709.2025.11294369.

[6] Y. Nie, Y. Kong, X. Dong, J. M. Mulvey, H. V. Poor, Q. Wen, and S. Zohren, "A Survey of Large Language Models for Financial Applications: Progress, Prospects and Challenges," arXiv:2406.11903, Jun. 2024.

[7] A. T. Khan, S. Li, and X. Cao, "Bridging Finance and AI: A Comprehensive Survey of Large Language Models in Financial System," *Digital Finance*, vol. 7, no. 4, 2025, doi: 10.1007/s42521-025-00146-3.

[8] Unde S. P., A. B. Ghule, R. S. Jaware, S. N. Kanawade, and Y. K. Koli, "AI-Based Real-Time Personal Finance Dashboard," *International Journal of Advanced Research Publications*, vol. 2, no. 6, pp. 1–11, Jun. 2026.

[9] M. S. Saini, P. Suri, D. Panwar, M. Sharma, S. Bagga, and V. Ahmad, "AI-Powered Personal Finance Management Applications," in *Proc. 2025 World Skills Conf. on Universal Data Analytics and Sciences (WorldS4AS)*, 2025, doi: 10.1109/WorldSUAS66815.2025.11199144.

[10] Patil et al., "Nexus Finance: AI-Powered Financial Goal Planner for Personalized Budgeting and Investment," *International Journal of Research and Innovation in Social Science (IJRISS)*, 2026. **[Reference details require verification** — full author list, volume, issue, pages and DOI were not recoverable from the supplied material. Fill in from the original before submission; do not invent them.**]**

**Project-internal documents** (cite as project material if referenced, never as third-party evidence): MEIKA Project Proposal (Discussion Draft); "Explainable AI-Based Personal Financial Copilot" project deck. The two copies of the latter are the same document.

---

# PART E — QUALITY-CONTROL VERIFICATION

Checked against the brief's Part 28 list.

| # | Check | Result |
|---|---|---|
| 1 | Every major claim supported by project material or literature | **Pass** |
| 2 | No reference-paper result presented as MEIKA's | **Pass** — 98% (Deepthi), 91%/78% (Badiger), 91%/88% (Patil) appear only in Slides 6/7 with attribution |
| 3 | No planned feature presented as completed | **Pass** — Copilot, JWT, rate limiting, goal forecasting, Price-Finder catalog all marked TO DO / ROADMAP |
| 4 | No fabricated dataset | **Pass** — 7 transactions / 6 categories, labelled prototype operational data |
| 5 | No fabricated user study | **Pass** — absence of a user study is listed as a limitation (Slide 23) |
| 6 | No fake deployment claimed | **Pass** |
| 7 | No unsupported accuracy claimed | **Pass** — no accuracy/precision/recall/F1/RMSE claimed for MEIKA anywhere |
| 8 | 91/100 clearly labelled a prototype output | **Pass** — Slides 13 and 19 |
| 9 | Implementation status preserved as briefed | **Pass** — Part 9 statuses used verbatim; divergence disclosed at the top and in Backup B1 |
| 10 | Research gap explicit | **Pass** — Slide 7 matrix |
| 11 | Contribution explicit | **Pass** — Slide 21 |
| 12 | XAI central | **Pass** — Slides 13, 14, 21 |
| 13 | Predictive budgeting clearly explained | **Pass** — Slide 15, with formulas |
| 14 | Goal forecasting marked per actual status | **Pass** — ROADMAP, not implemented |
| 15 | Conversational AI separated current/planned | **Pass** — Slide 17, planned and bounded |
| 16 | All relevant supplied papers incorporated | **Pass** — 10 sources; duplicates counted once |
| 17 | References consistent IEEE style | **Pass** — [10] flagged as needing verification |
| 18 | Suitable for a university Phase-I Review 1 | **Pass** |
| 19 | Slides concise; depth in speaker notes | **Pass** |
| 20 | No ML model claimed that isn't implemented | **Pass** — reference-method table in Part A.3 makes the distinction explicit |

**Two items needing your action before the review:**
1. **Reference [10]** — bibliographic details incomplete. Retrieve from the original paper.
2. **Slide 6** — if the ten-row table is unreadable at projector size, split into 6A / 6B rather than reducing the font.

**One judgement call flagged for you:** Slide 18 and Slide 25 present Review-1 statuses as briefed. If your panel expects the *present* state of the repository rather than the state on 14 August, lead with Backup Slide B1 instead of holding it in reserve.
