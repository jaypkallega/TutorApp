# MathTutor — Build Checkpoint v1.4
**Date:** May 2026  
**Status:** COMPLETE — All features built and verified  
**Total source files:** 79 (55 Python + 24 TypeScript/TSX)

---

## How to use this checkpoint

If you hit a usage limit and need to continue in a new conversation, paste this entire document as your first message. It gives the new session full context of what has been built, every file that exists, and what state the app is in.

---

## What the app is

A local home-network math tutoring app for a single family.
- Runs as a Python server on Windows 11
- Accessed from an iPad via Safari over home Wi-Fi
- Uses any LLM (OpenAI, Anthropic, Gemini) for AI features
- All data stays on the home network — no cloud storage

**Users:** One parent account (PIN login) + one child account (no login needed)  
**Primary device:** iPad with Apple Pencil  
**Grade level:** 7–8, CBSE, multi-subject

---

## Version history

### v1.0 — Foundation
- FastAPI backend with all models, schemas, JWT auth
- LiteLLM integration (OpenAI / Anthropic / Gemini)
- Tesseract + vision API OCR (hybrid mode)
- PDF parser (PyMuPDF + pdfplumber → LLM structure extraction)
- All API routes: auth, settings, textbooks, chapters, exercises, assignments, submissions, evaluations
- React + Vite + Tailwind frontend
- All pages: Setup, ParentLogin, Dashboard, Settings, TextbookLibrary, AssignmentBuilder, ChildHome, LearnMode, SolveWorkspace, Results
- StylusCanvas component (Apple Pencil, palm rejection, pressure)
- PWA manifest for iPad home screen

### v1.1 — Bug fixes + child self-assignment + multi-subject
- Fixed progress reset on iPad page refresh (sessionStorage persistence)
- Parent dashboard now shows assignment questions + per-question submission results
- Child self-assignment: `/child/self-assign` page, child role can create own assignments
- Multi-subject textbook support (Science, Physics, Chemistry, Biology, etc.)
- Results page now shows question text in each result card
- `is_self_assigned` flag on assignments

### v1.2 — Hybrid evaluation engine
- `structured_answer` JSON column on exercises (answer_type, sympy_expr, tolerance, rubric)
- LLM generates structured answer schema at exercise creation (not at eval time)
- `math_evaluator.py` — SymPy for numeric, algebraic, equation, fraction, expression_set
- `step_validator.py` — line-by-line derivation step checker
- `science_evaluator.py` — keyword rubric for conceptual answers
- `evaluator.py` — master routing layer (AI never decides correctness)
- `misconception_matcher.py` — 11 seeded Grade 8 misconceptions
- `answer_analyzer.py` — uses hybrid pipeline instead of raw LLM
- LLM now writes feedback only (cannot change the grade)
- `confidence` + `requires_parent_review` fields on evaluations
- ⚠️ flags in Results and Dashboard for low-confidence marks
- `migrate_v1_2.py`

### v1.3 — Visual display + AI teaching mode + book differentiation
- `visual_type` + `visual_data` columns on exercises
- `visual_extractor.py` — LLM vision extracts tables, number lines, bar graphs, geometry
- `VisualDisplay.tsx` component renders all visual types as SVG/HTML
- Page images served via `GET /api/v1/textbooks/{id}/page/{n}`
- `TeachMode.tsx` — Socratic AI teaching with 5 phases (Hook→Explore→Generalise→Example→Practice)
- `teaching_service.py` — phase progression, conversation management, Socratic prompts
- `concept_progress` table — mastery levels: not_started → introduced → practised → mastered
- `teaching_sessions` table
- Child Home updated with mastery indicators (○ ◑ ◕ ●) and "Learn with AI Tutor" section
- AssignmentBuilder: chapters now grouped by textbook with collapsible book headers
- `migrate_v1_3.py`

### v1.4 — Per-question draft saves + UI fixes
- `submission_drafts` table — one draft per assignment, stores per-question answers server-side
- `submission_drafts.py` API — start draft, save text/canvas/photo per question, submit
- SolveWorkspace completely rewritten:
  - Per-question **Save Answer** button (uploads to server immediately)
  - **Submit Test** button always visible at bottom
  - Page refresh safe — draft fetched from server on reload
  - Green ticks on saved question pills
  - Unanswered questions → confirmation dialog before submit
- SelfAssign fixes: book grouping, count selector (3/5/8/10/15), child can generate AI questions
- Duplicate questions prevented in assignment creation
- `exercises.py` — child role allowed to generate exercises (needed for self-assign)
- `chapter.py` schema — added `textbook_title` + `textbook_subject` fields (fixes book name display)
- `migrate_v1_4.py`

---

## Complete file list

### Backend — Models (`backend/models/`)
```
__init__.py          — imports all models (required before create_all)
user.py              — User (role: parent|child, parent_pin_hash)
settings.py          — AppSetting (key-value store for LLM config etc)
textbook.py          — Textbook (title, subject, grade, file_path, status)
chapter.py           — Chapter (textbook_id, approved, start/end_page)
concept.py           — Concept (chapter_id, explanation, ordering)
exercise.py          — Exercise (structured_answer, visual_type, visual_data)
assignment.py        — Assignment + AssignmentQuestion
submission.py        — Submission (input_mode, text_answer, processing_status)
submission_draft.py  — SubmissionDraft (per-question answers JSON, status)
evaluation.py        — Evaluation (per_question JSON, confidence, requires_parent_review)
progress.py          — ProgressState (resume payload — legacy)
concept_progress.py  — ConceptProgress + TeachingSession
misconception.py     — Misconception + StudentMisconceptionLog
```

### Backend — Schemas (`backend/schemas/`)
```
auth.py              — SetupRequest, LoginRequest, TokenResponse, SetupStatus
textbook.py          — TextbookOut, TextbookList
chapter.py           — ChapterOut (includes textbook_title, textbook_subject), ConceptOut, ChapterUpdate
exercise.py          — ExerciseOut, GenerateExercisesRequest
assignment.py        — AssignmentOut, AssignmentQuestionOut, CreateAssignmentRequest
submission.py        — SubmissionOut, SubmissionCreate
evaluation.py        — EvaluationOut, QuestionResult
settings.py          — SettingsOut, SettingsUpdate, LLMTestResult, NetworkInfo
```

### Backend — API Routes (`backend/api/v1/`)
```
auth.py              — setup, parent/login, child/session, status
settings.py          — get/update settings, llm/test, network-info
textbooks.py         — upload, list, get, delete, page/{n} image serving
chapters.py          — list (with textbook_title), get, patch, explain concept
exercises.py         — list, get, generate (child + parent allowed)
assignments.py       — list, create (child self-assign supported), get, archive
submission_drafts.py — start, get, save text/canvas/photo, submit
submissions.py       — legacy bulk submit (text/image/canvas)
evaluations.py       — get result, assignment submissions view, child history
misconceptions.py    — child misconception summary
teach.py             — session/start, session/message, progress, progress/{concept_id}
```

### Backend — Services (`backend/services/`)
```
llm_service.py       — LiteLLM wrapper, all prompts, generate_structured_answer()
                       STRUCTURE_PROMPT_TEMPLATE uses .replace() not .format()
                       (avoids JSON brace conflicts)
ocr_service.py       — local Tesseract + vision API + hybrid mode
teaching_service.py  — Socratic session management, phase progression, mastery updates
```

### Backend — Processing (`backend/processing/`)
```
pdf_parser.py        — PDF → images → text → LLM → save chapters/concepts/exercises
answer_analyzer.py   — submission processing: OCR → evaluate → save evaluation
evaluator.py         — master routing layer (deterministic first, LLM last)
math_evaluator.py    — SymPy: normalize_math_input(), evaluate_numeric/algebraic/
                       equation/fraction/expression_set()
step_validator.py    — split_into_steps(), validate_steps(), evaluate_multi_step()
science_evaluator.py — evaluate_conceptual() with keyword rubric
                       generate_rubric_for_question() called at creation time
misconception_matcher.py — seed_misconceptions(), match_misconceptions(),
                           log_misconception(), get_child_misconception_summary()
visual_extractor.py  — extract_visual_for_exercise() via LLM vision
                       get_page_image_path()
```

### Backend — Core
```
main.py              — FastAPI app, all routers, LAN middleware, lifespan
config.py            — .env loading, paths, SUPPORTED_SUBJECTS list
database.py          — SQLAlchemy engine, SessionLocal, get_db
deps.py              — get_current_user, require_parent, require_child
```

### Frontend — Pages (`frontend/src/pages/`)
```
SetupPage.tsx        — First-run: parent name, PIN, child name
                       Uses window.location.href after setup (not navigate())
                       so App.tsx re-checks setup status
ParentLoginPage.tsx  — PIN pad (number buttons + keyboard input)
parent/Dashboard.tsx — Expandable assignments → questions → per-question results
parent/Settings.tsx  — LLM config (provider/model/key/base_url), OCR mode, network info
parent/TextbookLibrary.tsx — Upload PDF, subject dropdown, view chapters, approve
parent/AssignmentBuilder.tsx — Chapters grouped by textbook (collapsible), generate AI Qs
child/Home.tsx       — Auto-session, parent assignments, self-practice, Learn with AI Tutor
child/TeachMode.tsx  — Concept selector (mastery dots) + Socratic chat interface
child/SelfAssign.tsx — Chapters grouped by book, count selector, generate AI Qs
child/SolveWorkspace.tsx — Per-question save + Submit Test (draft-based, server-safe)
child/Results.tsx    — Score circle, per-question cards with question+answer+feedback+misconceptions
```

### Frontend — Components (`frontend/src/components/`)
```
Layout.tsx           — Header nav, main container
LoadingSpinner.tsx   — Spinner with optional text
VisualDisplay.tsx    — Renders: table, number_line, bar_graph, pie_chart, geometry, page_image
canvas/StylusCanvas.tsx — HTML5 canvas, pointer events, palm rejection, pressure,
                          initialStrokes prop for restore
```

### Frontend — Other
```
App.tsx              — Route tree, setup-aware routing
api/client.ts        — Axios instance, auth interceptor, 401 redirect
store/authStore.ts   — Zustand: user, setUser, logout, isParent, isChild
main.tsx             — ReactDOM root, QueryClientProvider
index.css            — Tailwind + custom utilities (.card, .btn-primary, .input-field)
```

### Migration Scripts
```
migrate_v1_2.py      — exercises.structured_answer, evaluations.confidence/requires_parent_review,
                       misconceptions table, student_misconception_logs table
migrate_v1_3.py      — exercises.visual_type/visual_data, concept_progress table,
                       teaching_sessions table
migrate_v1_4.py      — submission_drafts table
```

---

## Database tables (complete list)

| Table | Purpose |
|---|---|
| users | Parent + child accounts |
| app_settings | LLM config, OCR mode, LAN mode |
| textbooks | Uploaded books with processing status |
| chapters | Extracted chapters (require parent approval) |
| concepts | Key concepts per chapter |
| exercises | Questions with structured_answer + visual_data |
| assignments | Parent-created or child self-assigned practice sets |
| assignment_questions | Join table (assignment ↔ exercises, ordered) |
| submission_drafts | In-progress per-question answers (v1.4) |
| submissions | Finalised submissions after Submit Test |
| evaluations | Marked results with confidence + misconceptions |
| progress_states | Legacy resume state |
| concept_progress | Mastery level per concept per child |
| teaching_sessions | Socratic session history |
| misconceptions | 11 seeded Grade 8 error patterns |
| student_misconception_logs | Tracks which errors each child triggers |

---

## Key known bugs / gotchas

1. **`STRUCTURE_PROMPT_TEMPLATE` uses `.replace()` not `.format()`** — the prompt contains JSON `{}` which breaks `.format()`. Fixed in v1.1. Do not change this back.

2. **`SetupPage.tsx` uses `window.location.href` not `navigate()`** — App.tsx fetches setup status once on load. After setup completes, a full page reload is needed so it re-checks. `navigate()` would keep the old state.

3. **`passlib` incompatibility with newer `bcrypt`** — `auth.py` uses `bcrypt` directly (not passlib). Do not re-introduce passlib.

4. **All migration scripts must be run in order** after extracting a new archive:
   ```
   python migrate_v1_2.py
   python migrate_v1_3.py
   python migrate_v1_4.py
   ```

5. **`pymupdf` requires Visual Studio Build Tools on Windows** — use `pip install pymupdf --only-binary=:all:` to get the pre-built wheel.

6. **Python 3.12 required** — Python 3.14 breaks pydantic-core (Rust build fails). The venv must use `py -3.12 -m venv venv`.

7. **Gemini LLM_BASE_URL must be blank** — LiteLLM handles Gemini routing internally. Setting a custom base_url breaks Gemini calls.

8. **`chapter.py` schema includes `textbook_title` and `textbook_subject`** — these are not DB columns, they are enriched at query time in `chapters.py`. The schema must declare them as `Optional[str] = None` or FastAPI will strip them from responses.

---

## Environment setup (Windows 11)

### Prerequisites
- Python 3.12.x (not 3.14) — download from python.org, check "Add to PATH"
- Node.js LTS (v20 or v22)
- Tesseract OCR — install to `C:\Program Files\Tesseract-OCR\`, add to system PATH
- Git (optional)

### First-time setup
```cmd
cd C:\Users\jayap\Mathtutorv1\mathtutor_v1.0_complete\mathtutor

py -3.12 -m venv venv
venv\Scripts\activate

pip install pymupdf --only-binary=:all:
pip install pillow --only-binary=:all:
pip install bcrypt==4.0.1
pip install sympy==1.12
pip install -r requirements.txt --only-binary=pymupdf,pillow

python migrate_v1_2.py
python migrate_v1_3.py
python migrate_v1_4.py

cd frontend
npm install
cd ..
```

### Daily start (development)
```cmd
start_dev.bat
```
Opens two windows:
- Backend: `http://localhost:8000` (and `http://192.168.0.178:8000` for iPad)
- Frontend: `http://localhost:5173` (use this in laptop browser for development)

### Daily start (production)
```cmd
start.bat
```
Serves everything from `:8000` (requires `npm run build` first).

### .env configuration
```env
LLM_PROVIDER=gemini
LLM_API_KEY=your-key-here
LLM_MODEL_NAME=gemini-1.5-flash
LLM_BASE_URL=              ← must be blank for Gemini
OCR_MODE=hybrid
LAN_ONLY_MODE=1
```

---

## Current network setup

- TP Link Omada (main router, dual WAN)
- TP Link Floor 1 router → Floor 2 router (AP mode, same subnet)
- Laptop IP: `192.168.0.178`
- iPad access URL: `http://192.168.0.178:8000`
- Windows Firewall rule: TCP port 8000 inbound, all profiles, named "MathTutor"
- Both floors work — AP mode means same `192.168.0.x` subnet throughout

---

## What to work on next (suggested)

1. **Per-question canvas restore** — when child navigates back to a saved canvas question, fetch the PNG from server and show a thumbnail + "re-draw to update" option
2. **Hint system** — child can tap "I need a hint" during solving; LLM gives one clue without the answer
3. **Parent weekly report** — PDF export of child progress (scores, mastery levels, recurring misconceptions)
4. **Adaptive difficulty** — if child scores >80% on an assignment, suggest harder questions next time
5. **Multiple children** — schema already supports it (assigned_to FK on assignments); needs UI changes

---

## Subjects supported

Mathematics, Science, Physics, Chemistry, Biology, Social Science, English, History, Geography

(defined in `backend/config.py` → `SUPPORTED_SUBJECTS`)

---

## LLM providers supported

| Provider | Setting value | Example model |
|---|---|---|
| OpenAI | `openai` | `gpt-4o`, `gpt-4o-mini` |
| Anthropic | `anthropic` | `claude-opus-4-5`, `claude-sonnet-4-5` |
| Google Gemini | `gemini` | `gemini-1.5-flash`, `gemini-1.5-pro` |
| Custom (Ollama etc.) | `custom` | Set LLM_BASE_URL to local endpoint |
