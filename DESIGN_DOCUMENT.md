# MathTutor — System Design Document

**Version:** 1.5  
**Date:** May 2026  
**Target:** Windows 11 Server + iPad Client  
**Stack:** Python / FastAPI · SQLite · React / TypeScript · Vite · Tailwind CSS

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [System Architecture](#2-system-architecture)
3. [Database Design](#3-database-design)
4. [Backend Architecture](#4-backend-architecture)
5. [Frontend Architecture](#5-frontend-architecture)
6. [AI & Evaluation Pipeline](#6-ai--evaluation-pipeline)
7. [Teaching Mode Architecture](#7-teaching-mode-architecture)
8. [Adaptive Difficulty Engine](#8-adaptive-difficulty-engine)
9. [Security & Network Model](#9-security--network-model)
10. [File Structure Reference](#10-file-structure-reference)
11. [API Reference](#11-api-reference)
12. [User Flows](#12-user-flows)
13. [Design Decisions & Rationale](#13-design-decisions--rationale)
14. [Known Limitations & Future Work](#14-known-limitations--future-work)

---

## 1. Product Overview

MathTutor is a **local home-network learning application** designed for a single family. It runs as a server on a Windows 11 laptop and is accessed via a browser on an iPad. It is not a cloud product — all data stays within the home network.

### 1.1 Core Purpose

The app enables a parent to:
- Upload school textbooks as PDFs
- Have those textbooks analysed by an AI to extract chapters, concepts, and exercises
- Create assignments for their child from those exercises
- Monitor the child's submissions, marks, and recurring mistakes

The app enables a child to:
- Learn concepts through an AI Socratic tutor before attempting exercises
- Solve assignments using drawing (Apple Pencil), typing, or photo upload
- Submit answers per-question with immediate save confirmation
- Request up to 3 Socratic hints per question (LLM never reveals the answer)
- Create their own self-practice assignments
- View detailed results with per-question feedback
- See personalised difficulty recommendations based on recent performance

### 1.2 Design Constraints

| Constraint | Decision |
|---|---|
| No internet required during use | All AI calls configurable; OCR can run locally |
| Single family, one child | No multi-tenant complexity; one parent + one child account |
| iPad as primary client device | Touch targets ≥ 44px, PWA installable, Apple Pencil via pointer events |
| Parent controls what child can do | Assignment policy settings; child cannot access explanations before attempting |
| Privacy | No data leaves the home network; LAN-only mode enforced by default |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────┐
│                  HOME NETWORK (LAN)                  │
│                                                     │
│  ┌──────────────────────┐    ┌────────────────────┐ │
│  │   Windows 11 Laptop  │    │       iPad         │ │
│  │                      │    │                    │ │
│  │  ┌────────────────┐  │    │  Safari / PWA      │ │
│  │  │  FastAPI       │◄─┼────┼─ http://192.168.x  │ │
│  │  │  :8000         │  │    │                    │ │
│  │  └───────┬────────┘  │    └────────────────────┘ │
│  │          │           │                           │
│  │  ┌───────▼────────┐  │    ┌────────────────────┐ │
│  │  │  SQLite DB     │  │    │  Vite Dev Server   │ │
│  │  │  mathtutor.db  │  │    │  :5173 (dev only)  │ │
│  │  └────────────────┘  │    └────────────────────┘ │
│  │                      │                           │
│  │  ┌────────────────┐  │    ┌────────────────────┐ │
│  │  │  data/         │  │    │  External AI API   │ │
│  │  │  textbooks/    │  │    │  OpenAI / Gemini / │ │
│  │  │  submissions/  │  │◄───┼─ Anthropic (HTTPS) │ │
│  │  │  page_images/  │  │    └────────────────────┘ │
│  │  └────────────────┘  │                           │
│  └──────────────────────┘                           │
└─────────────────────────────────────────────────────┘
```

### 2.1 Request Flow

```
iPad browser → GET/POST http://192.168.0.178:8000/api/v1/...
                    │
                    ▼
            LAN-only middleware (rejects non-LAN IPs)
                    │
                    ▼
            JWT auth middleware (Bearer token check)
                    │
                    ▼
            FastAPI route handler
                    │
            ┌───────┴────────┐
            ▼                ▼
        SQLite DB      Background task
        (sync ORM)     (PDF parsing /
                        evaluation)
                             │
                             ▼
                        LLM API call
                        (OpenAI/Gemini/
                         Anthropic)
```

### 2.2 Deployment Modes

**Development:** Two servers — FastAPI (`--reload`) on :8000, Vite dev server on :5173 with proxy to :8000.

**Production:** `npm run build` produces `frontend/dist/`. FastAPI serves static files from there. Single server on :8000.

---

## 3. Database Design

SQLite database at `data/mathtutor.db`. All tables are created by SQLAlchemy's `Base.metadata.create_all()` on startup. Schema changes via numbered migration scripts (`migrate_v1_2.py` etc.).

### 3.1 Entity Relationship Diagram

```
users
  │
  ├─── assignments (created_by, assigned_to → users.id)
  │         │
  │         ├─── assignment_questions → exercises
  │         ├─── submissions
  │         │         └─── evaluations
  │         └─── submission_drafts
  │
  ├─── concept_progress → concepts
  └─── teaching_sessions → concepts
       student_misconception_logs → misconceptions

textbooks
  └─── chapters
            └─── concepts
                      └─── exercises
                                └─── (structured_answer JSON)
                                └─── (visual_data JSON)
```

### 3.2 Table Definitions

#### `users`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| role | TEXT | `parent` or `child` |
| display_name | TEXT | |
| parent_pin_hash | TEXT | bcrypt hash, null for child |
| created_at | DATETIME | |
| last_seen_at | DATETIME | |

#### `app_settings`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| key | TEXT UNIQUE | e.g. `llm_provider`, `llm_api_key` |
| value | TEXT | |
| description | TEXT | |
| updated_at | DATETIME | |

Default keys seeded on startup: `llm_provider`, `llm_api_key`, `llm_model_name`, `llm_base_url`, `ocr_mode`, `lan_only_mode`, `app_version`.

#### `textbooks`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| title | TEXT | Entered by parent |
| subject | TEXT | Mathematics, Science, Physics, Chemistry, Biology, etc. |
| grade | INTEGER | |
| file_path | TEXT | Absolute path on server |
| upload_type | TEXT | `pdf` or `images` |
| page_count | INTEGER | Set after parsing |
| status | TEXT | `pending` → `processing` → `ready` / `error` |
| analysis_log | TEXT | Human-readable status message |
| created_at | DATETIME | |
| approved_at | DATETIME | |
| approved_by | INTEGER FK users | |

#### `chapters`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| textbook_id | INTEGER FK | |
| chapter_number | INTEGER | |
| title | TEXT | |
| summary | TEXT | LLM-generated |
| start_page | INTEGER | |
| end_page | INTEGER | |
| approved | BOOLEAN | Parent must approve before use |
| teaching_style | TEXT | Optional parent override |
| created_at | DATETIME | |

#### `concepts`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| chapter_id | INTEGER FK | |
| concept_name | TEXT | |
| explanation | TEXT | LLM-generated |
| textbook_method | TEXT | |
| alternate_method | TEXT | |
| difficulty_hint | TEXT | Common misconceptions |
| source_page_start | INTEGER | |
| source_page_end | INTEGER | |
| ordering | INTEGER | Display order within chapter |
| created_at | DATETIME | |

#### `exercises`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| chapter_id | INTEGER FK | |
| concept_id | INTEGER FK | nullable |
| source | TEXT | `textbook` or `ai_generated` |
| difficulty | TEXT | `easy`, `medium`, `hard` |
| exercise_type | TEXT | `calculation`, `word_problem`, `proof` |
| prompt | TEXT | The question text |
| expected_answer | TEXT | Freeform human-readable |
| expected_method | TEXT | |
| structured_answer | TEXT | JSON — for deterministic evaluation |
| visual_type | TEXT | `table`, `number_line`, `bar_graph`, `pie_chart`, `geometry`, `axes`, `page_image` |
| visual_data | TEXT | JSON — rendered by VisualDisplay component |
| source_page | INTEGER | |
| created_at | DATETIME | |

**`structured_answer` JSON schema (by answer_type):**
```json
// numeric
{"answer_type": "numeric", "canonical_value": "42", "sympy_expr": "42", "tolerance": 0.01, "unit": "cm"}

// algebraic
{"answer_type": "algebraic", "canonical_value": "2x+3", "sympy_expr": "2*x+3"}

// equation
{"answer_type": "equation", "canonical_value": "x=5", "sympy_expr": "x-5"}

// conceptual (science)
{"answer_type": "conceptual", "rubric": {
  "required_concepts": [{"keyword": "chlorophyll", "weight": 2, "synonyms": ["green pigment"]}],
  "optional_concepts": [],
  "min_required_score": 4,
  "max_score": 6
}}
```

#### `assignments`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| created_by | INTEGER FK users | parent or child |
| assigned_to | INTEGER FK users | always child |
| chapter_id | INTEGER FK | |
| title | TEXT | optional |
| question_count | INTEGER | |
| allowed_difficulties | TEXT | JSON array e.g. `["easy","medium"]` |
| explanation_policy | TEXT | `locked`, `after_attempt`, `always` |
| show_wrong_reasons | BOOLEAN | Show correct answers in results |
| due_date | DATETIME | nullable |
| status | TEXT | `active`, `completed`, `archived` |
| created_at | DATETIME | |

Note: `created_by == assigned_to` indicates a child self-assignment.

#### `assignment_questions`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| assignment_id | INTEGER FK | |
| exercise_id | INTEGER FK | |
| ordering | INTEGER | Display order |
| locked | BOOLEAN | |

#### `submission_drafts`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| assignment_id | INTEGER FK | |
| child_id | INTEGER FK | |
| answers | TEXT | JSON map: `{exercise_id: {mode, text, image_path, saved_at}}` |
| status | TEXT | `in_progress` → `submitted` |
| created_at | DATETIME | |
| updated_at | DATETIME | |

Only one `in_progress` draft per (child, assignment). Finalised on Submit Test.

#### `submissions`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| assignment_id | INTEGER FK | |
| child_id | INTEGER FK | |
| attempt_number | INTEGER | Increments per re-attempt |
| input_mode | TEXT | `text`, `canvas`, `image_upload` |
| image_path | TEXT | For canvas/image submissions |
| canvas_json | TEXT | Raw stroke data |
| text_answer | TEXT | JSON array of per-question answers |
| submitted_at | DATETIME | |
| processing_status | TEXT | `pending` → `processing` → `done` / `error` |

#### `evaluations`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| submission_id | INTEGER FK UNIQUE | |
| total_questions | INTEGER | |
| correct_count | INTEGER | |
| wrong_count | INTEGER | |
| skipped_count | INTEGER | |
| per_question | TEXT | JSON array of per-question result objects |
| overall_feedback | TEXT | LLM-generated summary |
| confidence | FLOAT | 0.0–1.0 aggregate confidence |
| requires_parent_review | BOOLEAN | True if any question has low confidence |
| low_confidence_questions | TEXT | JSON array of question indices |
| evaluated_at | DATETIME | |
| evaluated_by | TEXT | `hybrid`, `llm`, `sympy` |

**`per_question` item schema:**
```json
{
  "question_index": 0,
  "exercise_id": 42,
  "status": "correct|wrong|partial|skipped",
  "ocr_text": "student's extracted answer text",
  "feedback": "one sentence from LLM",
  "correct_answer": "shown if show_wrong_reasons=true",
  "marks": 1.0,
  "confidence": 0.97,
  "method": "sympy_simplify|keyword_rubric|llm_fallback",
  "requires_parent_review": false,
  "misconceptions": [
    {"topic": "Fractions", "diagnosis": "Added denominators directly", "remedy": "..."}
  ]
}
```

#### `misconceptions`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| subject | TEXT | |
| topic | TEXT | e.g. `Fractions`, `Indices` |
| pattern_type | TEXT | `sympy_check`, `string_pattern`, `step_error` |
| pattern | TEXT | Regex or SymPy expression |
| diagnosis | TEXT | Short name of the error |
| remedy | TEXT | Explanation shown to student |

Seeded with 11 Grade 8 misconceptions on startup.

#### `student_misconception_logs`
Tracks which misconceptions a child triggers over time for parent trend analysis.

#### `concept_progress`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| child_id | INTEGER FK | |
| concept_id | INTEGER FK | |
| mastery_level | TEXT | `not_started` → `introduced` → `practised` → `mastered` |
| teach_sessions_completed | INTEGER | |
| exercises_attempted | INTEGER | |
| exercises_correct | INTEGER | |
| unlocked_for_test | BOOLEAN | True after first session |
| last_interaction | DATETIME | |
| recommended_difficulty | TEXT | `easy`, `medium`, `hard` — set by adaptive engine |
| consecutive_promotions | INTEGER | Consecutive eval cycles above promotion threshold |
| consecutive_demotions | INTEGER | Consecutive eval cycles below demotion threshold |

Mastery thresholds: `introduced` = 1 session, `practised` = 3 sessions or 5+ correct, `mastered` = 5+ sessions and 80%+ accuracy.

Adaptive difficulty thresholds (see §8): promotion requires `avg_readiness ≥ 0.80` AND `last_readiness ≥ 0.75` for 2 consecutive cycles; demotion if `last_readiness < 0.45`.

#### `teaching_sessions`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| child_id | INTEGER FK | |
| concept_id | INTEGER FK | |
| phase | TEXT | `hook` → `explore` → `generalise` → `example` → `practice` → `complete` |
| messages | TEXT | JSON array of `{role, content, phase, timestamp}` |
| completed | BOOLEAN | |

---

## 4. Backend Architecture

### 4.1 Technology Stack

| Component | Choice | Reason |
|---|---|---|
| Web framework | FastAPI 0.111 | Async, auto-docs, Pydantic validation |
| ORM | SQLAlchemy 2.0 | Mature, sync sessions work for SQLite |
| Database | SQLite | Zero infrastructure, sufficient for single-family use |
| Auth | python-jose (JWT) + bcrypt | Stateless tokens, no session storage needed |
| LLM | LiteLLM 1.40 | Unified API for OpenAI, Anthropic, Gemini |
| OCR | pytesseract + vision API fallback | Local-first, upgrades automatically when needed |
| Math evaluation | SymPy 1.12 | Symbolic equivalence, not string comparison |
| PDF parsing | PyMuPDF + pdfplumber | PyMuPDF for images, pdfplumber for text |
| Task execution | FastAPI BackgroundTasks | Sufficient for single-user; no queue needed |

### 4.2 Application Startup Sequence

```
lifespan() called
    │
    ├── import backend.models  (registers all models with SQLAlchemy metadata)
    ├── Base.metadata.create_all(engine)  (creates tables if not exist)
    ├── _seed_default_settings()  (inserts default app_settings rows)
    └── seed_misconceptions()  (inserts 11 Grade 8 misconceptions if table empty)
```

### 4.3 Middleware Stack

Requests pass through this stack in order:

1. **LAN-only middleware** — rejects any request from a non-private IP address if `lan_only_mode=1`. Reads setting from DB on each request (cached implicitly by SQLite).
2. **CORS middleware** — allows all origins (safe because LAN-only enforces network boundary).
3. **JWT bearer auth** — implemented as FastAPI dependencies (`get_current_user`, `require_parent`, `require_child`) on individual routes, not global middleware.

### 4.4 Module Structure

```
backend/
├── main.py              — FastAPI app, middleware, router registration, lifespan
├── config.py            — .env loading, paths, constants, SUPPORTED_SUBJECTS
├── database.py          — SQLAlchemy engine, SessionLocal, get_db dependency
├── deps.py              — JWT auth dependencies
│
├── models/              — SQLAlchemy ORM models (one file per table)
├── schemas/             — Pydantic request/response models
│
├── api/v1/              — Route handlers (thin controllers)
│   ├── auth.py          — Setup, login, child session
│   ├── settings.py      — LLM config, OCR config, network info
│   ├── textbooks.py     — Upload, list, delete, serve page images
│   ├── chapters.py      — List, get, approve, explain concept
│   ├── exercises.py     — List, get, generate (AI)
│   ├── assignments.py   — Create (parent + child), list, archive
│   ├── submission_drafts.py — Start draft, save per-question, submit
│   ├── submissions.py   — Legacy bulk submission (canvas/image/text)
│   ├── evaluations.py   — Get results, assignment submission history
│   ├── misconceptions.py — Child misconception summary
│   └── teach.py         — Start session, send message, get progress
│
├── services/
│   ├── llm_service.py   — LiteLLM wrapper, all prompts, structured answer + hint generation
│   ├── ocr_service.py   — Tesseract + vision API fallback
│   └── teaching_service.py — Socratic session management, phase progression,
│                             recommended_difficulty injection into practice phase
│
└── processing/
    ├── pdf_parser.py        — PDF → images → text → LLM structure extraction
    ├── answer_analyzer.py   — Submission processing pipeline (OCR → eval → save)
    ├── evaluator.py         — Master routing layer (deterministic vs LLM)
    ├── math_evaluator.py    — SymPy numeric, algebraic, equation, fraction, set
    ├── step_validator.py    — Line-by-line derivation step checker
    ├── science_evaluator.py — Keyword rubric for conceptual answers
    ├── misconception_matcher.py — Pattern matching against known errors
    ├── visual_extractor.py  — Extract visual content from PDF pages (geometry,
    │                          cube_net, coordinate axes, compound polygons)
    └── adaptive.py          — 3-signal readiness formula, promotion/demotion logic
```

### 4.5 Background Task Pattern

Long-running operations run as FastAPI background tasks so HTTP requests return immediately:

```
POST /textbooks  →  return {status: "pending"}  →  background: process_textbook()
POST /submissions  →  return {status: "processing"}  →  background: process_submission()
POST /drafts/{id}/submit  →  return {submission_id}  →  background: process_submission()
```

Each background task opens its own `SessionLocal()` session (not the request's session, which closes after the response).

---

## 5. Frontend Architecture

### 5.1 Technology Stack

| Component | Choice |
|---|---|
| Framework | React 18 + TypeScript |
| Build tool | Vite 5 |
| Styling | Tailwind CSS 3 with custom design tokens |
| Routing | React Router v6 |
| State management | Zustand (auth store only) |
| Data fetching | axios with interceptors |
| Icons | lucide-react |

### 5.2 Auth State

Zustand store (`authStore.ts`) holds: `user` (id, name, role, token). Token persisted to `sessionStorage` so it survives page refresh but not a new browser session. On 401 response, axios interceptor clears store and redirects to login.

Child session is token-less from the child's perspective — the app calls `POST /auth/child/session` automatically on the child Home page if no token is present.

### 5.3 Route Structure

```
/setup                       → SetupPage (first-run only)
/parent/login                → ParentLoginPage (PIN pad)
/parent/dashboard            → ParentDashboard
/parent/settings             → SettingsPage
/parent/textbooks            → TextbookLibrary
/parent/assignments/new      → AssignmentBuilder

/child/home                  → ChildHome (auto-session)
/child/teach/:chapterId      → TeachMode (AI Socratic tutor)
/child/self-assign           → SelfAssign
/child/solve/:assignmentId   → SolveWorkspace (draft-based)
/child/results/:submissionId → Results (polls until done)
```

App root checks `/api/v1/auth/status` on load. If `setup_complete=false`, all routes render SetupPage. After setup, navigates to full route tree.

### 5.4 Component Tree

```
App
├── SetupPage
├── ParentLoginPage
├── Layout (header nav, main container)
│   ├── ParentDashboard
│   │   └── Expandable assignment cards with per-question results
│   ├── SettingsPage
│   ├── TextbookLibrary
│   │   └── Expandable chapter/concept cards
│   ├── AssignmentBuilder
│   │   └── Chapters grouped by textbook (collapsible)
│   ├── ChildHome
│   │   ├── Parent-assigned work
│   │   ├── Self-practice sessions
│   │   └── Learn with AI Tutor (chapters with mastery dots)
│   ├── TeachMode
│   │   ├── Concept selector (mastery indicators)
│   │   └── Chat interface (phase progress bar)
│   ├── SelfAssign
│   │   ├── Chapters grouped by textbook (collapsible)
│   │   └── Exercise picker with AI generate
│   ├── SolveWorkspace
│   │   ├── Question navigator pills
│   │   ├── VisualDisplay (if exercise has visual_data)
│   │   ├── StylusCanvas / textarea / photo upload
│   │   ├── Save Answer button (per-question)
│   │   └── Submit Test button (always visible)
│   └── Results
│       ├── ScoreCircle (SVG animated)
│       └── Per-question cards (question + answer + feedback + misconception)
│
└── VisualDisplay (standalone component)
    ├── TableVisual
    ├── NumberLineVisual (SVG)
    ├── BarGraphVisual (SVG)
    ├── PieChartVisual (SVG)
    ├── GeometryVisual (SVG — triangle, rectangle, circle, angle,
    │   ├── polygon / compound shapes (6+ vertices)
    │   └── CubeNetVisual (grid of squares with fold-line dashes)  [v1.5]
    ├── CoordinateAxesVisual (x-y grid, points, segments, polygon)  [v1.5]
    └── PageImageVisual (img from /api/v1/textbooks/{id}/page/{n})
```

### 5.5 PWA Configuration

`public/manifest.json` configures the app as an installable PWA:
- `display: standalone` — removes Safari chrome when added to home screen
- `orientation: any` — works in portrait and landscape
- Apple-specific meta tags for home screen icon and status bar

---

## 6. AI & Evaluation Pipeline

### 6.1 Design Principle

> **AI should assist evaluation. AI should not decide correctness.**

The LLM is used for three things only:
1. **Curriculum work** (at textbook upload time): extract structure, generate exercises, create keyword rubrics, generate structured answer schemas
2. **OCR interpretation** (at submission time): extract text from handwritten canvas or photo when Tesseract confidence is low
3. **Feedback writing** (after correctness is determined): write one encouraging sentence of feedback — the grade is already decided

The LLM never has the final word on whether an answer is correct.

### 6.2 Evaluation Routing

```
Student answer (text/canvas/photo)
         │
         ▼
    answer_analyzer.py
    ┌─────────────────────────────────────────┐
    │  1. OCR if canvas or photo              │
    │     local Tesseract → confidence check  │
    │     if low → vision API fallback        │
    │                                         │
    │  2. evaluator.py (per question)         │
    │     │                                   │
    │     ├── answer_type == numeric          │
    │     │   → math_evaluator (float diff)   │
    │     │                                   │
    │     ├── answer_type == algebraic        │
    │     │   → math_evaluator (sympy simplify│
    │     │      student - expected == 0)     │
    │     │                                   │
    │     ├── answer_type == equation         │
    │     │   → math_evaluator (sympy solve,  │
    │     │      compare solution sets)       │
    │     │                                   │
    │     ├── answer_type == fraction         │
    │     │   → math_evaluator (nsimplify)    │
    │     │                                   │
    │     ├── answer_type == multi_step       │
    │     │   → step_validator               │
    │     │      (check each line preserves  │
    │     │       solution set)              │
    │     │                                   │
    │     ├── answer_type == conceptual       │
    │     │   → science_evaluator            │
    │     │      (keyword rubric matching)   │
    │     │                                   │
    │     └── canvas/photo or unknown type   │
    │         → LLM fallback (restricted     │
    │           prompt — OCR mode only)      │
    │                                         │
    │  3. Confidence score assigned           │
    │     < 0.6 → requires_parent_review      │
    │                                         │
    │  4. misconception_matcher               │
    │     (regex against known error patterns)│
    │                                         │
    │  5. LLM: write feedback sentence only   │
    │     (grade already decided — cannot     │
    │      change correctness)               │
    │                                         │
    │  6. Save Evaluation to DB               │
    └─────────────────────────────────────────┘
```

### 6.3 SymPy Input Normalisation

Student notation is normalised before SymPy parsing:

| Input | Normalised |
|---|---|
| `2x` | `2*x` |
| `x^2` | `x**2` |
| `2(x+3)` | `2*(x+3)` |
| `√x` | `sqrt(x)` |
| `x²` | `x**2` (unicode superscripts) |
| `\frac{2}{3}` | `(2)/(3)` (LaTeX) |

### 6.4 Confidence Scoring

| Evaluator | Confidence |
|---|---|
| SymPy exact match | 0.97–0.99 |
| SymPy with parse error fallback | 0.40–0.50 |
| Keyword rubric (clear pass/fail) | 0.90 |
| Keyword rubric (borderline 40–70%) | 0.75 |
| Step validator | 0.90–0.95 |
| LLM fallback (canvas/photo) | 0.75 |
| Unknown type / unparseable | 0.30 |

When confidence < 0.60, `requires_parent_review = true` is set on the evaluation and a ⚠️ flag appears in the parent dashboard and child results.

### 6.5 OCR Pipeline

```
Image input
    │
    ├── Mode: local
    │   └── pytesseract (PSM 6, eng+equ config)
    │       → preprocess: grayscale, contrast +2x, binarise
    │
    ├── Mode: vision_api
    │   └── LLM vision endpoint (gpt-4o / gemini-1.5-pro)
    │       → prompt: "transcribe handwritten math faithfully"
    │
    └── Mode: hybrid (default)
        ├── Try local OCR
        ├── confidence >= 60% → use result
        └── confidence < 60% → vision API fallback
```

### 6.6 LLM Configuration

All LLM calls go through `llm_service.py` which reads provider/model/key from `app_settings` table at call time. LiteLLM translates to the correct API:

| Provider setting | LiteLLM model string |
|---|---|
| `openai` / `gpt-4o` | `gpt-4o` |
| `anthropic` / `claude-opus-4-5` | `anthropic/claude-opus-4-5` |
| `gemini` / `gemini-1.5-flash` | `gemini/gemini-1.5-flash` |
| `custom` / any | `custom/{model}` with `base_url` |

### 6.7 Textbook Processing Pipeline

```
PDF upload
    │
    ├── 1. Save to data/textbooks/
    ├── 2. Start background task: process_textbook()
    ├── 3. Render pages to PNG (PyMuPDF, 150 DPI)
    │      → data/page_images/textbook_{id}/page_NNNN.png
    ├── 4. Extract text (pdfplumber)
    │      → if total chars < 50 × pages: run Tesseract on images
    ├── 5. Send to LLM in 30-page chunks
    │      → STRUCTURE_PROMPT_TEMPLATE (subject + grade aware)
    │      → Returns JSON: chapters → concepts → exercises
    ├── 6. For each exercise: generate structured_answer JSON
    │      → one LLM call per exercise (at creation time, not eval time)
    ├── 7. Save chapters, concepts, exercises to DB
    └── 8. Update textbook.status = "ready"
```

---

## 7. Teaching Mode Architecture

### 7.1 Socratic Phase Model

Each concept session progresses through six phases:

```
hook → explore → generalise → example → practice → complete
```

| Phase | Purpose | AI behaviour | Advances after |
|---|---|---|---|
| hook | Spark curiosity | Real-world question, no mention of concept name | 1 student exchange |
| explore | Discover patterns | "What do you notice?" — never states the rule | 2 exchanges |
| generalise | State the rule | "How would you explain this to a friend?" | 1 exchange |
| example | Work through a problem | Lets student drive steps, asks "what next?" | 1 exchange |
| practice | Try independently | One problem, evaluates approach then answer | 2 exchanges |
| complete | Wrap up | Summarises using student's own words | — |

### 7.2 Socratic Rules (enforced via system prompt)

These rules are embedded in the system prompt and apply across all phases:
1. **Never give the answer or the rule directly**
2. **Ask ONE question at a time**
3. **Praise correct observations specifically** ("That's exactly right — you noticed that...")
4. **Never say "wrong"** — redirect with "Interesting, what happens if we try..."
5. **Maximum 4 sentences per response**
6. **Phase-specific instructions** override the base prompt

### 7.3 Phase Advancement Logic

Phase advances when the student has sent at least `PHASE_MIN_EXCHANGES[phase]` messages in the current phase. The LLM does not control advancement — it is deterministic based on exchange count. This prevents the LLM from getting "stuck" in a phase or skipping phases.

### 7.4 Mastery Progression

```
not_started
    │
    └── first session completed
            │
            ▼
        introduced  (concept unlocked for test assignments)
            │
            └── 3 sessions OR 5 correct exercises
                    │
                    ▼
                practised
                    │
                    └── 5 sessions AND 80%+ exercise accuracy
                            │
                            ▼
                        mastered
```

---

## 8. Adaptive Difficulty Engine

### 8.1 Design Philosophy

The engine operates as a **recommendation layer**, not a hidden automatic switch. Parents always see a badge explaining *why* a difficulty change is suggested. The system never silently changes difficulty on parent-created assignments — only on child self-assignments and in the AI Tutor practice phase.

### 8.2 Three Signals

| Signal | Weight | Source |
|---|---|---|
| Assignment accuracy | 0.6 | `exercises_correct / exercises_attempted` per concept |
| Independence (hint usage) | 0.2 | Inverse of hint fraction used per session |
| Stability (confidence flags) | 0.2 | Absence of parent-review flags and major misconceptions |

Combined: `readiness = 0.6 × accuracy + 0.2 × independence + 0.2 × stability`

### 8.3 Promotion / Demotion Rules

```
If avg_readiness ≥ 0.80 AND last_readiness ≥ 0.75
  → consecutive_promotions += 1
  → if consecutive_promotions ≥ 2: move up one difficulty level

If last_readiness < 0.45
  → consecutive_demotions += 1
  → if consecutive_demotions ≥ 2: move down one difficulty level

If active misconception flag exists
  → block promotion (misconception must clear first)
```

### 8.4 Integration Points

| Where | Behaviour |
|---|---|
| **AI Teach Mode — practice phase** | `teaching_service.py` fetches `recommended_difficulty` and injects it into the LLM system prompt so the AI calibrates its practice question difficulty |
| **Child SelfAssign** | Shows a recommendation badge with plain-English reason (e.g. "You got 9/10 last time — try hard?") |
| **Parent AssignmentBuilder** | Shows a "Difficulty Insights" panel per chapter with concept-level recommendations and explanations |
| **Parent Dashboard** | Difficulty Insights card summarising concepts ready for promotion and those needing consolidation |

### 8.5 Hint Tracking

- Each exercise allows a maximum of **3 hints**.
- Hints are Socratic — the LLM prompt explicitly prohibits revealing the answer or any sub-answer.
- Hint usage count is stored per session and fed into the independence signal.
- Parents can see hint usage per assignment in the Dashboard.

---

## 9. Security & Network Model

### 9.1 Authentication

- **Parent**: PIN-based login. PIN hashed with bcrypt, stored in `users.parent_pin_hash`. JWT token returned on success (8-hour expiry).
- **Child**: No PIN required. `POST /auth/child/session` returns a token automatically. This is intentional — the child should not be blocked by authentication.
- **Token storage**: `sessionStorage` (not `localStorage`) — clears when browser tab closes.

### 9.2 Authorisation

Three dependency levels:
- `get_current_user` — any valid JWT
- `require_parent` — JWT with `role=parent`
- `require_child` — JWT with `role=child`

Notable permissions:
- Child **can** create self-assignments (but `explanation_policy=always` is blocked)
- Child **can** generate AI exercises (needed for self-assign)
- Child **cannot** approve chapters, view settings, delete textbooks

### 9.3 LAN Enforcement

The `lan_only_middleware` checks every request's client IP against private network prefixes: `10.`, `172.`, `192.168.`, `127.`, `::1`. If the IP doesn't match any prefix and `lan_only_mode=1`, the request is rejected with HTTP 403.

This setting is stored in the DB (not just `.env`) so it can be toggled from the Settings UI without restarting the server.

### 9.4 API Key Security

The LLM API key is:
- Stored in `app_settings` table (not in code)
- Masked in `GET /settings` responses (shows last 4 characters only)
- Never included in frontend responses
- Never logged

---

## 10. File Structure Reference

```
mathtutor/
├── .env.example             — environment variable template
├── .gitignore
├── requirements.txt         — Python dependencies
├── start.bat                — production launcher
├── start_dev.bat            — development launcher (opens two windows)
├── migrate_v1_2.py          — DB migration: structured_answer, evaluations confidence
├── migrate_v1_3.py          — DB migration: visual_type, concept_progress, teaching_sessions
├── migrate_v1_4.py          — DB migration: submission_drafts
├── migrate_v1_5.py          — DB migration: recommended_difficulty, consecutive_promotions/demotions
├── CHECKPOINT_v1.1.md       — build state checkpoint
├── CHECKPOINT_v1.4.md       — build state checkpoint (v1.4)
│
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── deps.py
│   ├── models/              — 12 SQLAlchemy model files
│   ├── schemas/             — 8 Pydantic schema files
│   ├── api/v1/              — 11 route files
│   ├── services/            — llm_service, ocr_service, teaching_service
│   └── processing/          — pdf_parser, answer_analyzer, evaluator,
│                              math_evaluator, step_validator,
│                              science_evaluator, misconception_matcher,
│                              visual_extractor, adaptive
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── postcss.config.js
│   ├── public/
│   │   ├── manifest.json    — PWA manifest
│   │   ├── favicon.svg
│   │   └── icons/           — PWA icons (192px, 512px)
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── index.css        — Tailwind + custom utilities
│       ├── api/client.ts    — Axios instance with auth interceptor
│       ├── store/authStore.ts
│       ├── components/
│       │   ├── Layout.tsx
│       │   ├── LoadingSpinner.tsx
│       │   ├── VisualDisplay.tsx
│       │   └── canvas/StylusCanvas.tsx
│       └── pages/
│           ├── SetupPage.tsx
│           ├── ParentLoginPage.tsx
│           ├── parent/Dashboard, Settings, TextbookLibrary, AssignmentBuilder
│           └── child/Home, TeachMode, SelfAssign, SolveWorkspace, Results
│
└── data/                    — created at runtime, excluded from git
    ├── mathtutor.db
    ├── textbooks/           — uploaded PDF files
    ├── page_images/         — rendered PDF pages (PNG)
    ├── submissions/         — canvas drawings, uploaded photos, draft images
    └── cache/
```

---

## 11. API Reference

All endpoints are prefixed `/api/v1`. Authentication required unless noted.

### Auth (`/auth`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/auth/status` | None | Check if setup is complete |
| POST | `/auth/setup` | None | First-run: create parent + child |
| POST | `/auth/parent/login` | None | Parent PIN login → JWT |
| POST | `/auth/child/session` | None | Child auto-session → JWT |

### Settings (`/settings`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/settings` | Parent | Get all settings (API key masked) |
| PUT | `/settings` | Parent | Update settings |
| POST | `/settings/llm/test` | Parent | Test LLM connection |
| GET | `/settings/network-info` | Parent | Get LAN IP for iPad |

### Textbooks (`/textbooks`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/textbooks` | Parent | List all textbooks |
| POST | `/textbooks` | Parent | Upload PDF (starts background analysis) |
| GET | `/textbooks/{id}` | Parent | Get single textbook |
| PATCH | `/textbooks/{id}` | Parent | Update textbook title inline |
| DELETE | `/textbooks/{id}` | Parent | Delete textbook + file |
| GET | `/textbooks/{id}/page/{n}` | Any | Serve page image PNG |

### Chapters (`/chapters`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/chapters` | Any | List chapters (optionally filter by textbook_id) |
| GET | `/chapters/{id}` | Any | Get chapter with concepts |
| PATCH | `/chapters/{id}` | Parent | Approve, update teaching style |
| POST | `/chapters/{id}/explain` | Any | Get AI explanation for a concept |
| GET | `/chapters/{id}/difficulty-recommendation` | Any | Get adaptive difficulty insights for a chapter |

### Exercises (`/exercises`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/exercises` | Any | List (filter by chapter_id, difficulty) |
| GET | `/exercises/{id}` | Any | Get single exercise |
| POST | `/exercises/generate` | Any | Generate AI exercises for a chapter |

### Assignments (`/assignments`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/assignments` | Any | List (parent sees all, child sees active only) |
| POST | `/assignments` | Any | Create assignment (child: self-assign only) |
| GET | `/assignments/{id}` | Any | Get with questions |
| PATCH | `/assignments/{id}/archive` | Any | Archive |

### Submission Drafts (`/drafts`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/drafts/start` | Child | Get or create in-progress draft |
| GET | `/drafts/{id}` | Child | Get draft with saved answers summary |
| PUT | `/drafts/{id}/text` | Child | Save text answer for one question |
| PUT | `/drafts/{id}/canvas` | Child | Save canvas drawing (PNG upload) |
| PUT | `/drafts/{id}/photo` | Child | Save photo upload |
| POST | `/drafts/{id}/submit` | Child | Finalise → create submission → trigger eval |

### Evaluations (`/evaluations`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/evaluations/submission/{id}` | Any | Get evaluation (polls during processing) |
| GET | `/evaluations/assignment/{id}/submissions` | Any | Parent view: all submissions + results |
| GET | `/evaluations/child/{id}/history` | Any | All submissions history for a child |

### Teaching (`/teach`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/teach/session/start` | Child | Start or resume a teaching session |
| POST | `/teach/session/message` | Child | Send message, get AI response |
| GET | `/teach/progress` | Any | Get mastery progress for all concepts (includes `chapter_id`, `last_interaction`) |
| GET | `/teach/progress/{concept_id}` | Any | Get progress for one concept |
| POST | `/teach/hint` | Child | Request a Socratic hint (max 3 per question; never reveals answer) |

### Misconceptions (`/misconceptions`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/misconceptions/child/{id}/summary` | Any | Misconception frequency for a child |

---

## 12. User Flows

### 11.1 First Run (Parent)

```
Open http://localhost:5173
    → /setup  (App detects setup_complete=false)
    → Enter parent name, PIN (4-8 digits), child name
    → POST /auth/setup  → redirected to /parent/settings
    → Enter LLM provider + API key
    → Test Connection  → POST /settings/llm/test
    → Save Settings
    → Go to Textbook Library
    → Upload PDF  → background analysis begins
    → Wait for "Analysis complete: N chapters found"
    → Expand textbook  → approve relevant chapters
    → Go to New Assignment
    → Select chapter → select questions → Create Assignment
```

### 12.2 Child Learning Session

```
Open app on iPad (http://192.168.0.178:8000)
    → /child/home  (auto-session, no login needed)
    → Horizontal chapter strip under "Learn with AI Tutor"
       (last-accessed chapter highlighted with "Continue →" badge)
    → Tap a chapter chip → /child/teach/{chapterId}
    → Select concept (shows mastery indicator)
    → AI opens with a hook question
    → Converse for 5 phases (Hook → Practice)
       (practice phase uses recommended_difficulty to calibrate AI questions)
    → Session completes → concept marked "introduced"
    → Return to home
    → Start an assignment  → /child/solve/{assignmentId}
    → Per question: draw/type/photo → Save Answer
    → If stuck: tap "Need a hint?" → up to 3 Socratic nudges per question
    → Navigate between questions freely
    → Submit Test → /child/results/{submissionId}
    → Wait for marking (5-15 seconds)
    → See score, per-question feedback, misconception hints
```

### 12.3 Parent Review

```
Login → /parent/dashboard
    → See all assignments
    → Expand assignment to see questions
    → Expand submission to see per-question results
    → ⚠️ flag on low-confidence answers → can review manually
    → See "My child triggered fraction addition error 3 times" alert
    → See Difficulty Insights card:
       "Integers: ready to move to Hard (scored 88%, low hint usage)"
       "Fractions: stay at Medium (flagged misconception: denominator addition)"
    → Click textbook title in TextbookLibrary to rename it inline (PATCH)
```

---

## 13. Design Decisions & Rationale

### 12.1 Why SQLite and not PostgreSQL?

This is a single-family home app with one parent and one child. Peak concurrent requests: 2. SQLite with `check_same_thread=False` handles this trivially. PostgreSQL would add infrastructure complexity (service management, connection strings) with zero benefit.

### 12.2 Why not store sessions server-side?

JWT tokens in `sessionStorage` are stateless and require no server-side session table. For a home app where the parent is the admin, token revocation is not a concern. The 8-hour expiry is sufficient.

### 12.3 Why LiteLLM instead of direct SDKs?

Switching LLM provider (OpenAI → Gemini → Anthropic) is a single settings change with LiteLLM. Without it, switching providers would require code changes. Since the parent configures the provider from the Settings UI, the routing abstraction is essential.

### 12.4 Why SymPy for evaluation instead of just LLM?

LLMs are inconsistent graders. `2x/4` and `x/2` are mathematically identical but textually different — an LLM may mark one wrong. `simplify(2*x/4 - x/2) == 0` is always correct. The hybrid architecture uses LLM only where deterministic systems genuinely cannot work (handwriting interpretation, science conceptual answers without a rubric).

### 12.5 Why per-question draft saves instead of one bulk submission?

Three reasons: (1) Page refresh on iPad loses in-memory canvas strokes — server-side draft saves survive any crash or refresh. (2) Allows the child to see confirmation that each answer was received. (3) Future: allows per-question auto-evaluation and hints as the child works.

### 12.6 Why no sentence-transformers for semantic similarity?

For Grade 8 science answers, weighted keyword rubrics achieve 85-90% accuracy. sentence-transformers would require downloading a 90MB+ PyTorch model, with known Windows/venv conflicts. The marginal accuracy gain (to ~92%) is not worth the installation complexity for a home app.

### 13.7 Why Socratic teaching instead of direct explanation?

Research in educational psychology (Bloom, Vygotsky) consistently shows that guided discovery produces stronger retention than passive reading. The app has the textbook content — the AI's job is to make the child think, not to replace the book. Direct explanation is available in LearnMode (the original static mode); TeachMode is the adaptive alternative.

### 13.8 Why hints cap at 3 and never reveal the answer?

The goal is scaffolded independence, not answer retrieval. Three hints match Vygotsky's zone of proximal development — enough guidance to unlock the next step, not so much that the child stops thinking. Hint count feeds into the independence signal of the adaptive engine, so a child who always uses all 3 hints will see a lower readiness score even if they answer correctly.

### 13.9 Why recommendation-first adaptive difficulty (not automatic)?

Automatic difficulty switching behind the scenes is confusing for both parent and child — the child doesn't know why questions changed; the parent doesn't know why the assignment is harder than they set. The recommendation model keeps the parent as the final authority. The only place difficulty switches automatically is in the AI Tutor practice phase, which is a conversation, not a graded assignment — a safe context for experimentation.

### 13.10 Why a horizontal scroll strip for chapter selection?

A 2-column grid of chapter cards forces the child to scroll ~500px just to find Chapter 5. A horizontal strip collapses the entire section to ~96px regardless of chapter count, keeping assignments and self-practice visible above the fold. The "Continue →" badge reduces friction further — the child can resume exactly where they left off with one tap.

---

## 14. Known Limitations & Future Work

### Current Limitations

| Area | Limitation |
|---|---|
| Multi-child | Only one child account supported. Adding a second child requires code changes. |
| Per-question canvas drafts | Canvas drafts are stored as PNG server-side. When navigating back to a saved canvas question, the drawing is not restored (only the "saved" indicator shows). |
| OCR accuracy | Tesseract struggles with messy handwriting. Vision API (Gemini/GPT-4o) is significantly better but costs API tokens per submission. |
| Step validator | Only validates linear equation solving reliably. Geometry proofs, simultaneous equations, and calculus steps are not validated. |
| Geometry visual — multiple choice | Questions of the form "which of the following figures is a net?" cannot show labelled diagram options (A/B/C/D). The exercise generator now blocks these and converts them to constructive questions. A future image-option MCQ format would require a UI type change. |
| Adaptive signals — hint tracking | Hint count is currently tracked at session level; per-exercise precision would give a more accurate independence signal. |
| Offline operation | LLM API calls require internet. Local-only mode (Tesseract OCR + a local LLM like Ollama) is partially supported via `custom` provider but not tested. |

### Feature Status Summary (v1.5)

| Feature | Status | Notes |
|---|---|---|
| Hint system (3 Socratic hints/question) | ✅ Done | `llm_service.generate_hint()`, wired in `SolveWorkspace` |
| Geometry SVG renderer — triangles, circles, angles | ✅ Done | `VisualDisplay.GeometryVisual` |
| Geometry SVG renderer — cube nets | ✅ Done | `CubeNetVisual` with fold-line dashes |
| Geometry SVG renderer — coordinate axes | ✅ Done | `CoordinateAxesVisual` with grid, arrows, points |
| Geometry SVG renderer — compound shapes | ✅ Done | 6+ vertex polygon path, example in extractor prompt |
| Geometry question generation guardrails | ✅ Done | `GENERATE_EXERCISES_PROMPT` blocks unrenderable MCQ |
| Adaptive difficulty engine | ✅ Done | `adaptive.py`, 3-signal readiness, consecutive logic |
| Adaptive difficulty — parent dashboard insights | ✅ Done | Difficulty Insights card in `Dashboard.tsx` |
| Adaptive difficulty — child self-assign badges | ✅ Done | Recommendation panel in `SelfAssign.tsx` |
| Adaptive difficulty — AI tutor calibration | ✅ Done | `teaching_service.py` injects `recommended_difficulty` |
| Textbook title inline editing | ✅ Done | PATCH `/textbooks/{id}` + inline UI in `TextbookLibrary.tsx` |
| Compact child topic selection (horizontal strip) | ✅ Done | `Home.tsx` — scrollable chip strip grouped by textbook |
| "Continue →" last-accessed chapter badge | ✅ Done | Derived from `last_interaction` in progress data |

### Planned Future Work

| Feature | Priority | Notes |
|---|---|---|
| Multiple child accounts | Medium | Schema supports it (assigned_to FK), UI does not |
| Per-question canvas restore | Low | Fetch image from server on navigate back |
| Visual identification MCQ (nets from options) | Medium | Requires new exercise type + image option UI |
| Streak and gamification | Low | Daily streak counter, badges for mastery milestones |
| Progress export (PDF report) | Medium | Parent weekly report with charts |
| Alembic migrations | Medium | Replace manual migration scripts with proper Alembic versioning |
| Per-exercise hint tracking | Low | More precise independence signal for adaptive engine |
| Offline LLM (Ollama) | Low | Full offline operation via local model |
| Multiple subjects per session | Low | Currently each textbook has one subject; mixed assignments across subjects |
