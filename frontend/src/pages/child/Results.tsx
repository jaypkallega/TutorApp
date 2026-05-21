import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import Layout from '../../components/Layout'
import api from '../../api/client'
import { CheckCircle2, XCircle, AlertCircle, RotateCcw, Home, AlertTriangle, Info } from 'lucide-react'

interface Misconception { topic: string; diagnosis: string; remedy: string }

interface QuestionResult {
  question_index: number; exercise_id: number
  status: 'correct' | 'wrong' | 'partial' | 'skipped'
  feedback: string | null; correct_answer: string | null
  marks: number; ocr_text: string | null
  question_prompt: string; difficulty: string
  confidence: number; method: string
  requires_parent_review: boolean
  misconceptions: Misconception[]
}

interface Evaluation {
  total_questions: number; correct_count: number
  wrong_count: number; skipped_count: number; score_percent: number
  per_question: QuestionResult[]; overall_feedback: string | null
  confidence: number; requires_parent_review: boolean
  low_confidence_questions: number[]
}

const STATUS_CONFIG = {
  correct: { icon: <CheckCircle2 className="text-green-500 shrink-0 mt-0.5" size={20} />, border: 'border-green-100 bg-green-50', badge: 'bg-green-100 text-green-700', label: 'Correct ✓' },
  wrong:   { icon: <XCircle className="text-red-400 shrink-0 mt-0.5" size={20} />, border: 'border-red-100 bg-red-50', badge: 'bg-red-100 text-red-600', label: 'Incorrect' },
  partial: { icon: <AlertCircle className="text-amber-400 shrink-0 mt-0.5" size={20} />, border: 'border-amber-100 bg-amber-50', badge: 'bg-amber-100 text-amber-700', label: 'Partial ½' },
  skipped: { icon: <AlertCircle className="text-gray-300 shrink-0 mt-0.5" size={20} />, border: 'border-gray-100 bg-gray-50', badge: 'bg-gray-100 text-gray-500', label: 'Skipped' },
}

const METHOD_LABELS: Record<string, string> = {
  sympy_simplify: 'Math engine', numeric_tolerance: 'Math engine',
  sympy_solve: 'Math engine', sympy_rational: 'Math engine',
  keyword_rubric: 'Keyword check', step_validator: 'Step validator',
  llm_fallback: 'AI assisted', auto_detect: 'Auto detect', skipped: 'Not answered',
}

function ScoreCircle({ percent }: { percent: number }) {
  const color = percent >= 80 ? '#22c55e' : percent >= 50 ? '#f59e0b' : '#ef4444'
  const r = 54; const circ = 2 * Math.PI * r
  const offset = circ - (percent / 100) * circ
  return (
    <svg width="140" height="140" viewBox="0 0 140 140">
      <circle cx="70" cy="70" r={r} fill="none" stroke="#f3f4f6" strokeWidth="12" />
      <circle cx="70" cy="70" r={r} fill="none" stroke={color} strokeWidth="12"
        strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
        transform="rotate(-90 70 70)" style={{ transition: 'stroke-dashoffset 1s ease' }} />
      <text x="70" y="65" textAnchor="middle" fontSize="26" fontWeight="bold" fill={color}>{percent}%</text>
      <text x="70" y="85" textAnchor="middle" fontSize="11" fill="#9ca3af">score</text>
    </svg>
  )
}

export default function Results() {
  const { submissionId } = useParams<{ submissionId: string }>()
  const navigate = useNavigate()
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [polling, setPolling] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let attempts = 0
    const poll = async () => {
      try {
        const r = await api.get(`/evaluations/submission/${submissionId}`)
        if (r.data.status === 'processing') {
          attempts++
          if (attempts > 60) { setPolling(false); setError('Evaluation is taking too long. Please try again.') }
          return
        }
        setEvaluation(r.data)
        setPolling(false)
      } catch (e: any) {
        setError(e.response?.data?.detail || 'Could not load results')
        setPolling(false)
      }
    }
    poll()
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [submissionId])

  if (polling) return (
    <Layout title="Results">
      <div className="text-center py-20">
        <div className="w-16 h-16 border-4 border-primary-100 border-t-primary-500 rounded-full animate-spin mx-auto mb-4" />
        <p className="text-lg font-medium text-gray-700">Marking your work...</p>
        <p className="text-gray-400 text-sm mt-2">This usually takes 5–15 seconds</p>
        <p className="text-gray-300 text-xs mt-1">(The marking engine is checking your answers)</p>
      </div>
    </Layout>
  )

  if (error) return (
    <Layout title="Results">
      <div className="card text-center py-10">
        <XCircle size={40} className="mx-auto mb-3 text-red-400" />
        <p className="text-gray-600">{error}</p>
        <Link to="/child/home" className="btn-primary mt-4 inline-block">Back to Home</Link>
      </div>
    </Layout>
  )

  if (!evaluation) return <Layout title="Results"><div className="card text-center text-gray-400">Loading...</div></Layout>

  const { per_question, score_percent, correct_count, total_questions, overall_feedback } = evaluation
  const isGreat = score_percent >= 80; const isOk = score_percent >= 50

  return (
    <Layout title="Results">
      {/* Parent review warning */}
      {evaluation.requires_parent_review && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 mb-4 flex items-center gap-2 text-sm text-amber-700">
          <AlertTriangle size={16} className="shrink-0" />
          <span>Some answers could not be marked with full confidence. Your parent has been notified to review.</span>
        </div>
      )}

      {/* Score hero */}
      <div className="card text-center mb-6">
        <div className="flex justify-center"><ScoreCircle percent={score_percent} /></div>
        <h2 className="text-2xl font-bold mt-2 text-gray-800">
          {isGreat ? '🎉 Excellent work!' : isOk ? '👍 Good effort!' : '💪 Keep practising!'}
        </h2>
        <p className="text-gray-500 mt-1">{correct_count} out of {total_questions} correct</p>
        {overall_feedback && <p className="mt-3 text-gray-600 text-sm max-w-md mx-auto leading-relaxed">{overall_feedback}</p>}
        <div className="flex justify-center gap-3 mt-4 flex-wrap">
          <span className="bg-green-100 text-green-700 text-sm px-3 py-1 rounded-full font-medium">✓ {evaluation.correct_count} correct</span>
          <span className="bg-red-100 text-red-600 text-sm px-3 py-1 rounded-full font-medium">✗ {evaluation.wrong_count} wrong</span>
          {evaluation.skipped_count > 0 && <span className="bg-gray-100 text-gray-500 text-sm px-3 py-1 rounded-full font-medium">— {evaluation.skipped_count} skipped</span>}
        </div>
      </div>

      {/* Per-question breakdown */}
      <div className="space-y-4 mb-6">
        {per_question.map((qr, i) => {
          const config = STATUS_CONFIG[qr.status] ?? STATUS_CONFIG.skipped
          const methodLabel = METHOD_LABELS[qr.method] || qr.method
          const lowConf = qr.confidence < 0.6
          return (
            <div key={i} className={`rounded-2xl border p-4 ${config.border} ${qr.requires_parent_review ? 'ring-2 ring-amber-200' : ''}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-gray-700 text-sm">Question {i + 1}</span>
                  {qr.requires_parent_review && <AlertTriangle size={14} className="text-amber-500" title="Parent review needed" />}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400" title={`Evaluated by: ${methodLabel}`}>{methodLabel}</span>
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${config.badge}`}>{config.label}</span>
                </div>
              </div>

              {/* Question prompt */}
              {qr.question_prompt && (
                <div className="bg-white rounded-xl p-3 mb-3 border border-gray-100">
                  <p className="text-xs text-gray-400 font-medium mb-1 uppercase tracking-wide">Question</p>
                  <p className="text-gray-800 text-sm leading-relaxed">{qr.question_prompt}</p>
                </div>
              )}

              <div className="flex items-start gap-3">
                {config.icon}
                <div className="flex-1 space-y-2">
                  {qr.ocr_text && (
                    <div className="p-2 bg-white rounded-lg border text-sm text-gray-600">
                      <span className="text-xs text-gray-400 block mb-0.5 font-medium">Your answer:</span>
                      <span className="font-mono">{qr.ocr_text}</span>
                    </div>
                  )}
                  {qr.feedback && <p className="text-sm text-gray-600 leading-relaxed">{qr.feedback}</p>}
                  {qr.correct_answer && qr.status !== 'correct' && (
                    <div className="p-2 bg-green-50 rounded-lg border border-green-100 text-sm">
                      <span className="text-xs text-green-600 font-semibold block mb-0.5">Correct answer:</span>
                      <span className="text-green-800 font-mono">{qr.correct_answer}</span>
                    </div>
                  )}

                  {/* Misconceptions */}
                  {qr.misconceptions && qr.misconceptions.length > 0 && (
                    <div className="bg-orange-50 border border-orange-100 rounded-xl p-3">
                      <p className="text-xs font-semibold text-orange-700 mb-1 flex items-center gap-1">
                        <Info size={12} /> Common mistake detected: {qr.misconceptions[0].diagnosis}
                      </p>
                      <p className="text-xs text-orange-700 leading-relaxed">{qr.misconceptions[0].remedy}</p>
                    </div>
                  )}

                  {/* Low confidence notice */}
                  {lowConf && (
                    <p className="text-xs text-gray-400 italic flex items-center gap-1">
                      <AlertTriangle size={12} /> Answer was unclear — your parent can review this mark.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex gap-3">
        <Link to="/child/home" className="btn-secondary flex-1 flex items-center justify-center gap-2">
          <Home size={18} /> Home
        </Link>
        <button onClick={() => navigate(-1)} className="btn-primary flex-1 flex items-center justify-center gap-2">
          <RotateCcw size={18} /> Try Again
        </button>
      </div>
    </Layout>
  )
}
