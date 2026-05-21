# MathTutor — Build Checkpoint v1.1
**Date:** May 2026
**Status:** COMPLETE — All 6 issues fixed, 6 files syntax-verified

---

## What was fixed in v1.1

### Fix 1 — Progress reset on iPad page refresh
**File:** `frontend/src/pages/child/SolveWorkspace.tsx`
- All answers (text, canvas strokes, photo names) saved to `sessionStorage` keyed by `assignmentId`
- Restored automatically on page load
- Cleared only after successful submission
- Shows a "continuing where you left off" banner when resuming

### Fix 2 — Parent can see assigned questions and child submissions
**File:** `frontend/src/pages/parent/Dashboard.tsx`
**File:** `backend/api/v1/evaluations.py` (new endpoint added)
- Dashboard now shows each assignment as an expandable card
- Expanding reveals all questions with prompts, difficulty, expected answers
- Each submission is also expandable to show per-question results with feedback
- New API endpoint: `GET /api/v1/evaluations/assignment/{id}/submissions`

### Fix 3 — Child self-assignment feature
**Files added/modified:**
- `frontend/src/pages/child/SelfAssign.tsx` (new page)
- `frontend/src/pages/child/Home.tsx` (new "My Practice" section)
- `frontend/src/components/Layout.tsx` (+ icon in child nav bar)
- `backend/api/v1/assignments.py` (child role can now POST assignments)
- `frontend/src/App.tsx` (new `/child/self-assign` route)

Child restrictions enforced:
- Can only assign to themselves
- `explanation_policy` is forced to `after_attempt` (never `always`)
- Parent dashboard shows self-assigned sessions with "Self" badge
- Self-assignments visible to parent in Dashboard

### Fix 4 — Multi-subject textbook support
**Files modified:**
- `backend/config.py` — `SUPPORTED_SUBJECTS` list added
- `backend/api/v1/textbooks.py` — accepts `subject` form field
- `backend/services/llm_service.py` — prompts now use `{subject}` and `{grade}`
- `backend/processing/pdf_parser.py` — passes subject/grade to LLM
- `frontend/src/pages/parent/TextbookLibrary.tsx` — Subject dropdown added

Supported subjects: Mathematics, Science, Physics, Chemistry, Biology,
Social Science, English, History, Geography

### Fix 5 — Results page now shows the question
**Files:** `backend/api/v1/evaluations.py`, `frontend/src/pages/child/Results.tsx`
- Evaluation endpoint now joins with `exercises` table to fetch prompts
- Each question result card shows: question text → child's answer → feedback → correct answer

### Fix 6 — Result analysis speed (5–7 seconds)
This is **normal**. LLM API round-trip + inference = 3–10 seconds.
No code change needed. Loading screen updated to say "5–15 seconds".

---

## Changed files summary
```
backend/
  api/v1/evaluations.py    — enriched results + new assignment submissions endpoint
  api/v1/assignments.py    — child self-assignment support
  api/v1/textbooks.py      — subject field added
  config.py                — SUPPORTED_SUBJECTS list
  services/llm_service.py  — subject-aware prompts
  processing/pdf_parser.py — passes subject/grade to LLM

frontend/src/
  App.tsx                         — /child/self-assign route added
  components/Layout.tsx           — child nav + icon
  pages/child/Home.tsx            — My Practice section
  pages/child/SolveWorkspace.tsx  — sessionStorage progress persistence
  pages/child/Results.tsx         — question text in each result card
  pages/child/SelfAssign.tsx      — NEW: child self-assignment page
  pages/parent/Dashboard.tsx      — expandable questions + submissions
  pages/parent/TextbookLibrary.tsx — subject dropdown
```

---

## How to apply v1.1 (extract over existing install)
```
1. Stop both servers (Ctrl+C in both windows)
2. Extract mathtutor_v1.1_fixes.tar.gz over your existing folder
   (overwrite all files — data/ folder is excluded so DB is safe)
3. Restart both servers:
   Window 1: venv\Scripts\activate && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   Window 2: cd frontend && npm run dev
```

---

## Complete file list (cumulative from v1.0 + v1.1)
All 77 files present (76 from v1.0 + SelfAssign.tsx added).
