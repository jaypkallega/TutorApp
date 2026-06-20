import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout'
import LoadingSpinner from '../../components/LoadingSpinner'
import StylusCanvas, { StylusCanvasHandle } from '../../components/canvas/StylusCanvas'
import VisualDisplay from '../../components/VisualDisplay'
import api from '../../api/client'
import {
  ChevronLeft, ChevronRight, PenLine, Type, Camera,
  CheckCircle2, Send, Save, AlertCircle, Clock, Lightbulb, X
} from 'lucide-react'

interface Exercise {
  id: number; prompt: string; difficulty: string
  exercise_type: string | null; visual_type?: string | null; visual_data?: string | null
}
interface AssignmentQuestion {
  id: number; exercise_id: number; ordering: number; exercise: Exercise | null
}
type InputMode = 'canvas' | 'text' | 'photo'

// For MCQ exercises
interface MCQOption {
  label: string
  visual: object
}
interface MCQVisualData {
  type: 'mcq_options'
  options: MCQOption[]
  correct_option?: string
}

interface SavedAnswer {
  mode: InputMode
  saved_at: string
  text_preview?: string | null
  has_image?: boolean
}

const DIFF_COLOR: Record<string, string> = {
  easy: 'bg-green-100 text-green-700',
  medium: 'bg-amber-100 text-amber-700',
  hard: 'bg-red-100 text-red-700',
}

function formatTime(iso: string) {
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
  catch { return '' }
}

export default function SolveWorkspace() {
  const { assignmentId } = useParams<{ assignmentId: string }>()
  const navigate = useNavigate()
  const canvasRef = useRef<StylusCanvasHandle>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const [questions, setQuestions] = useState<AssignmentQuestion[]>([])
  const [currentQ, setCurrentQ] = useState(0)
  const [loading, setLoading] = useState(true)
  const [inputMode, setInputMode] = useState<InputMode>('canvas')
  
  // MCQ-specific state
  const [selectedOption, setSelectedOption] = useState<string | null>(null)

  // Draft state
  const [draftId, setDraftId] = useState<number | null>(null)
  const [savedAnswers, setSavedAnswers] = useState<Record<string, SavedAnswer>>({})
  const [exerciseOrder, setExerciseOrder] = useState<number[]>([])

  // Per-question UI state
  const [textInput, setTextInput] = useState('')
  const [photoFile, setPhotoFile] = useState<File | null>(null)
  const [photoName, setPhotoName] = useState('')

  // Loading states
  const [saving, setSaving] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [saveError, setSaveError] = useState('')

  // Hint state
  const [hintsUsed, setHintsUsed] = useState<Record<string, number>>({})
  const [hintText, setHintText] = useState<string | null>(null)
  const [hintLoading, setHintLoading] = useState(false)
  const [hintError, setHintError] = useState('')
  const MAX_HINTS = 3

  // -------------------------------------------------------------------------
  // Init: load assignment + start/resume draft
  // -------------------------------------------------------------------------
  useEffect(() => {
    const init = async () => {
      try {
        const [aRes, dRes] = await Promise.all([
          api.get(`/assignments/${assignmentId}`),
          api.post('/drafts/start', { assignment_id: Number(assignmentId) }),
        ])
        setQuestions(aRes.data.questions || [])
        setDraftId(dRes.data.draft_id)
        setSavedAnswers(dRes.data.answers || {})
        setExerciseOrder(dRes.data.exercise_order || [])
        // Restore hint counts from server-side draft
        const restored: Record<string, number> = {}
        for (const [exId, ans] of Object.entries(dRes.data.answers || {})) {
          const a = ans as any
          if (a.hints_used) restored[exId] = a.hints_used
        }
        setHintsUsed(restored)
      } catch {
        navigate('/child/home')
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [assignmentId, navigate])

  const question = questions[currentQ]
  const exercise = question?.exercise
  const total = questions.length
  const exId = question?.exercise_id

  // Reset per-question inputs when navigating to a new question
  useEffect(() => {
    setTextInput('')
    setPhotoFile(null)
    setPhotoName('')
    setSaveError('')
    setHintText(null)
    setHintError('')
    setSelectedOption(null)  // Reset MCQ selection
    // Restore text input if previously saved
    if (exId && savedAnswers[String(exId)]?.mode === 'text') {
      setTextInput(savedAnswers[String(exId)].text_preview || '')
    }
  }, [currentQ, exId])

  const goTo = (idx: number) => setCurrentQ(idx)

  // -------------------------------------------------------------------------
  // Save answer for current question
  // -------------------------------------------------------------------------
  const saveAnswer = async () => {
    if (!draftId || !exId) return
    setSaving(true)
    setSaveError('')

    try {
      // Handle MCQ mode
      if (exercise && (exercise.visual_type === 'mcq_options' || exercise.exercise_type === 'visual_mcq')) {
        if (!selectedOption) { setSaveError('Please select an option before saving.'); return }
        const fd = new FormData()
        fd.append('exercise_id', String(exId))
        fd.append('text', selectedOption)  // Store letter as text answer
        await api.put(`/drafts/${draftId}/text`, fd)
        setSavedAnswers((prev) => ({
          ...prev,
          [String(exId)]: { mode: 'text', saved_at: new Date().toISOString(), text_preview: `Option ${selectedOption}` },
        }))
        
      } else if (inputMode === 'text') {
        if (!textInput.trim()) { setSaveError('Please write something before saving.'); return }
        const fd = new FormData()
        fd.append('exercise_id', String(exId))
        fd.append('text', textInput.trim())
        await api.put(`/drafts/${draftId}/text`, fd)
        setSavedAnswers((prev) => ({
          ...prev,
          [String(exId)]: { mode: 'text', saved_at: new Date().toISOString(), text_preview: textInput.slice(0, 80) },
        }))

      } else if (inputMode === 'canvas') {
        const dataUrl = canvasRef.current?.getImageDataURL()
        if (!dataUrl) { setSaveError('Nothing drawn yet.'); return }
        // Check canvas is not blank (all white)
        const strokes = canvasRef.current?.getCanvasData()
        if (!strokes || strokes.strokes.length === 0) { setSaveError('Please draw your answer before saving.'); return }
        // Convert data URL to Blob
        const res = await fetch(dataUrl)
        const blob = await res.blob()
        const fd = new FormData()
        fd.append('exercise_id', String(exId))
        fd.append('canvas_image', blob, `canvas_${exId}.png`)
        await api.put(`/drafts/${draftId}/canvas`, fd)
        setSavedAnswers((prev) => ({
          ...prev,
          [String(exId)]: { mode: 'canvas', saved_at: new Date().toISOString(), has_image: true },
        }))

      } else if (inputMode === 'photo') {
        if (!photoFile) { setSaveError('Please take or select a photo first.'); return }
        const fd = new FormData()
        fd.append('exercise_id', String(exId))
        fd.append('photo', photoFile)
        await api.put(`/drafts/${draftId}/photo`, fd)
        setSavedAnswers((prev) => ({
          ...prev,
          [String(exId)]: { mode: 'photo', saved_at: new Date().toISOString(), has_image: true },
        }))
      }

      // Auto-advance to next unanswered question
      const nextUnanswered = questions.findIndex(
        (q, i) => i > currentQ && !savedAnswers[String(q.exercise_id)]
      )
      if (nextUnanswered !== -1) {
        setTimeout(() => setCurrentQ(nextUnanswered), 400)
      }

    } catch (e: any) {
      setSaveError(e.response?.data?.detail || 'Save failed. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  // -------------------------------------------------------------------------
  // Request a hint
  // -------------------------------------------------------------------------
  const requestHint = async () => {
    if (!draftId || !exId) return
    const used = hintsUsed[String(exId)] ?? 0
    if (used >= MAX_HINTS) return
    setHintLoading(true)
    setHintError('')
    try {
      // Pass current text answer if available
      const currentAnswer = inputMode === 'text' ? textInput : ''
      const r = await api.post(`/drafts/${draftId}/hint`, {
        exercise_id: exId,
        current_answer: currentAnswer,
      })
      setHintText(r.data.hint)
      setHintsUsed(prev => ({ ...prev, [String(exId)]: r.data.hints_used }))
    } catch (e: any) {
      setHintError(e.response?.data?.detail || 'Could not get a hint. Please try again.')
    } finally {
      setHintLoading(false)
    }
  }

  // -------------------------------------------------------------------------
  // Submit entire test
  // -------------------------------------------------------------------------
  const submitTest = async () => {
    if (!draftId) return
    const savedCount = Object.keys(savedAnswers).length
    if (savedCount === 0) {
      alert('Please save at least one answer before submitting.')
      return
    }
    const unansweredCount = total - savedCount
    if (unansweredCount > 0) {
      const ok = confirm(
        `${unansweredCount} question${unansweredCount > 1 ? 's' : ''} not yet answered.\n\nSubmit anyway? Unanswered questions will be marked as skipped.`
      )
      if (!ok) return
    }
    setSubmitting(true)
    try {
      const r = await api.post(`/drafts/${draftId}/submit`)
      navigate(`/child/results/${r.data.submission_id}`)
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Submission failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  if (loading) return <Layout title="Test"><LoadingSpinner text="Loading your test..." /></Layout>
  if (!exercise) return (
    <Layout title="Test">
      <div className="card text-center text-gray-400 py-10">No questions found.</div>
    </Layout>
  )

  const savedCount = Object.keys(savedAnswers).length
  const currentSaved = savedAnswers[String(exId)]
  const allAnswered = savedCount === total

  return (
    <Layout title={`Question ${currentQ + 1} of ${total}`}>

      {/* Progress bar */}
      <div className="mb-1">
        <div className="flex justify-between text-xs text-gray-400 mb-1">
          <span>{savedCount} of {total} saved</span>
          <span>{Math.round((savedCount / total) * 100)}%</span>
        </div>
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div className="h-full bg-green-400 rounded-full transition-all duration-500"
            style={{ width: `${(savedCount / total) * 100}%` }} />
        </div>
      </div>

      {/* Question navigator pills */}
      <div className="flex gap-1.5 my-4 overflow-x-auto pb-1">
        {questions.map((q, i) => {
          const isSaved = !!savedAnswers[String(q.exercise_id)]
          const isCurrent = i === currentQ
          return (
            <button key={q.id} onClick={() => goTo(i)}
              className={`w-10 h-10 rounded-full shrink-0 font-semibold text-sm transition-all flex items-center justify-center ${
                isCurrent
                  ? 'bg-primary-500 text-white ring-2 ring-primary-300'
                  : isSaved
                  ? 'bg-green-100 text-green-700 hover:bg-green-200'
                  : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
              }`}>
              {isSaved && !isCurrent ? <CheckCircle2 size={16} /> : i + 1}
            </button>
          )
        })}
      </div>

      {/* Question card */}
      <div className="card mb-4">
        <div className="flex items-center justify-between mb-3">
          <span className={`text-xs font-semibold px-2 py-1 rounded-full ${DIFF_COLOR[exercise.difficulty] || 'bg-gray-100 text-gray-600'}`}>
            {exercise.difficulty}
          </span>
          {exercise.exercise_type && (
            <span className="text-xs text-gray-400 capitalize">{exercise.exercise_type.replace('_', ' ')}</span>
          )}
        </div>
        <p className="text-gray-800 text-lg leading-relaxed whitespace-pre-line">{exercise.prompt}</p>
        {exercise.visual_data && (
          <VisualDisplay visualData={exercise.visual_data} visualType={exercise.visual_type} />
        )}
      </div>

      {/* ── HINT SYSTEM ── */}
      {(() => {
        const used = hintsUsed[String(exId)] ?? 0
        const remaining = MAX_HINTS - used
        const exhausted = used >= MAX_HINTS
        return (
          <div className="mb-4">
            {/* Hint button */}
            {!exhausted && (
              <button
                id={`hint-btn-q${currentQ}`}
                onClick={requestHint}
                disabled={hintLoading}
                className="flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-xl border-2 border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100 disabled:opacity-50 transition-all"
              >
                {hintLoading
                  ? <><div className="w-4 h-4 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" /> Getting hint…</>
                  : <><Lightbulb size={15} />
                    {used === 0 ? 'Need a hint?' : used === MAX_HINTS - 1 ? '⚠️ Last hint' : 'Another hint'}
                    <span className="text-xs text-amber-500 font-normal">({remaining} of {MAX_HINTS} left)</span>
                  </>}
              </button>
            )}
            {exhausted && (
              <p className="text-xs text-gray-400 flex items-center gap-1">
                <Lightbulb size={12} /> No hints remaining for this question.
              </p>
            )}

            {/* Hint callout */}
            {hintText && (
              <div className="mt-2 flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
                <Lightbulb size={16} className="text-amber-500 shrink-0 mt-0.5" />
                <p className="flex-1 text-sm text-amber-800 leading-relaxed">{hintText}</p>
                <button onClick={() => setHintText(null)} className="text-amber-400 hover:text-amber-600 shrink-0">
                  <X size={14} />
                </button>
              </div>
            )}

            {/* Hint error */}
            {hintError && (
              <p className="mt-1 text-xs text-red-500">{hintError}</p>
            )}
          </div>
        )
      })()}

      {/* Already-saved banner */}
      {currentSaved && (
        <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-xl px-4 py-2.5 mb-4">
          <CheckCircle2 size={16} className="text-green-500 shrink-0" />
          <div className="flex-1 text-sm text-green-700">
            <span className="font-medium">Answer saved</span>
            <span className="text-green-500 ml-1">at {formatTime(currentSaved.saved_at)}</span>
            {currentSaved.text_preview && (
              <span className="text-green-600 ml-2 font-mono">— {currentSaved.text_preview}</span>
            )}
            {currentSaved.has_image && (
              <span className="text-green-600 ml-2">— {currentSaved.mode === 'canvas' ? '🖊 drawing' : '📷 photo'}</span>
            )}
          </div>
          <span className="text-xs text-green-400">Draw again to update</span>
        </div>
      )}

      {/* MCQ Option Cards — replaces input mode selector for visual_mcq */}
      {(exercise.visual_type === 'mcq_options' || exercise.exercise_type === 'visual_mcq') && (() => {
        let mcqData: MCQVisualData | null = null
        try {
          mcqData = exercise.visual_data 
            ? (typeof exercise.visual_data === 'string' ? JSON.parse(exercise.visual_data) : exercise.visual_data)
            : null
        } catch {}
        
        if (!mcqData || mcqData.type !== 'mcq_options') return null
        
        const isSaved = !!currentSaved
        return (
          <div className="mb-4">
            <p className="text-sm text-gray-500 mb-2">Select the correct option:</p>
            <div className="grid grid-cols-2 gap-3">
              {mcqData.options.map((opt, idx) => {
                const label = opt.label?.toUpperCase() || String.fromCharCode(65 + idx)
                const isSelected = selectedOption === label
                return (
                  <button
                    key={idx}
                    onClick={() => !isSaved && setSelectedOption(label)}
                    disabled={isSaved}
                    className={`relative p-3 rounded-xl border-2 transition-all text-left ${
                      isSelected 
                        ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-200' 
                        : 'border-gray-200 bg-white hover:border-gray-300'
                    } ${isSaved ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
                  >
                    <div className={`absolute top-2 left-2 w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs
                      ${isSelected ? 'bg-primary-500 text-white' : 'bg-gray-100 text-gray-600'}`}>
                      {label}
                    </div>
                    <div className="pt-7">
                      {/* Compact visual — no Figure header inside a small card */}
                      <VisualDisplay visualData={opt.visual} />
                    </div>
                  </button>
                )
              })}
            </div>
            {isSaved && (
              <p className="text-xs text-green-600 mt-2 flex items-center gap-1">
                <CheckCircle2 size={12} /> You selected option {selectedOption}
              </p>
            )}
          </div>
        )
      })()}

      {/* Input mode selector — hidden for MCQ exercises */}
      {(exercise.visual_type !== 'mcq_options' && exercise.exercise_type !== 'visual_mcq') && (
        <div className="flex gap-2 mb-4">
          {([
            { mode: 'canvas' as InputMode, icon: <PenLine size={16} />, label: 'Draw' },
            { mode: 'text' as InputMode, icon: <Type size={16} />, label: 'Type' },
            { mode: 'photo' as InputMode, icon: <Camera size={16} />, label: 'Photo' },
          ]).map(({ mode, icon, label }) => (
            <button key={mode} onClick={() => setInputMode(mode)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                inputMode === mode ? 'bg-primary-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
              {icon} {label}
            </button>
          ))}
        </div>
      )}

      {/* Answer area — hidden for MCQ (handled by option cards above) */}
      {(exercise.visual_type !== 'mcq_options' && exercise.exercise_type !== 'visual_mcq') && (
        <div className="mb-4">
          {inputMode === 'canvas' && (
            // key resets canvas for each question
            <StylusCanvas
              key={`canvas-q${currentQ}`}
              ref={canvasRef}
              width={900} height={320} strokeWidth={3}
            />
          )}

          {inputMode === 'text' && (
            <textarea
              className="input-field resize-none text-base" rows={6}
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder="Type your answer here. Show your working step by step."
            />
          )}

          {inputMode === 'photo' && (
            <div>
              <div
                className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center cursor-pointer hover:border-primary-300 transition-all"
                onClick={() => fileRef.current?.click()}
              >
                {photoName ? (
                  <div>
                    <div className="text-3xl mb-2">📷</div>
                    <p className="font-medium text-gray-700">{photoName}</p>
                    <p className="text-sm text-gray-400 mt-1">Tap to change</p>
                  </div>
                ) : (
                  <div>
                    <Camera size={36} className="mx-auto mb-2 text-gray-300" />
                    <p className="text-gray-500 font-medium">Take a photo or choose from gallery</p>
                    <p className="text-xs text-gray-400 mt-1">Works with iPad camera & Apple Pencil</p>
                  </div>
                )}
              </div>
              <input ref={fileRef} type="file" accept="image/*" capture="environment"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) { setPhotoFile(f); setPhotoName(f.name) }
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* Save error */}
      {saveError && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-xl px-4 py-2.5 mb-4 text-sm text-red-600">
          <AlertCircle size={16} className="shrink-0" /> {saveError}
        </div>
      )}

      {/* Save Answer button */}
      <button
        onClick={saveAnswer}
        disabled={saving}
        className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl font-semibold text-base mb-4 transition-all ${
          currentSaved
            ? 'bg-green-50 text-green-700 border-2 border-green-200 hover:bg-green-100'
            : 'bg-primary-500 text-white hover:bg-primary-600'
        } disabled:opacity-50`}
      >
        {saving ? (
          <><div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin" /> Saving...</>
        ) : currentSaved ? (
          <><Save size={18} /> Update Answer</>
        ) : (
          <><Save size={18} /> Save Answer</>
        )}
      </button>

      {/* Navigation */}
      <div className="flex gap-3 mb-6">
        <button onClick={() => goTo(currentQ - 1)} disabled={currentQ === 0}
          className="btn-secondary flex items-center gap-1 px-4">
          <ChevronLeft size={18} />
        </button>
        <button onClick={() => goTo(currentQ + 1)} disabled={currentQ === total - 1}
          className="btn-secondary flex-1 flex items-center justify-center gap-2">
          Next question <ChevronRight size={18} />
        </button>
      </div>

      {/* Submit Test — always visible at bottom */}
      <div className="border-t border-gray-100 pt-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm text-gray-500 flex items-center gap-1.5">
            <Clock size={14} />
            {savedCount} of {total} question{total !== 1 ? 's' : ''} answered
          </div>
          {allAnswered && (
            <span className="text-xs text-green-600 font-medium flex items-center gap-1">
              <CheckCircle2 size={12} /> All answered!
            </span>
          )}
        </div>
        <button
          onClick={submitTest}
          disabled={submitting || savedCount === 0}
          className={`w-full flex items-center justify-center gap-2 py-4 rounded-xl font-bold text-base transition-all ${
            allAnswered
              ? 'bg-green-500 text-white hover:bg-green-600'
              : 'bg-gray-800 text-white hover:bg-gray-900'
          } disabled:opacity-40`}
        >
          {submitting ? (
            <><div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" /> Submitting...</>
          ) : (
            <><Send size={18} /> Submit Test</>
          )}
        </button>
        {savedCount === 0 && (
          <p className="text-xs text-gray-400 text-center mt-2">Save at least one answer to submit</p>
        )}
      </div>
    </Layout>
  )
}
