import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import Layout from '../../components/Layout'
import LoadingSpinner from '../../components/LoadingSpinner'
import api from '../../api/client'
import { BookOpen, Plus, CheckCircle2, Clock, AlertCircle, ChevronDown, ChevronRight, User } from 'lucide-react'

interface Assignment {
  id: number; title: string | null; status: string
  question_count: number; created_at: string; is_self_assigned: boolean
}

interface QuestionResult {
  question_index: number; status: string; feedback: string | null
  correct_answer: string | null; ocr_text: string | null; question_prompt: string
}

interface SubmissionDetail {
  id: number; attempt_number: number; submitted_at: string
  processing_status: string
  evaluation: {
    correct_count: number; total_questions: number; score_percent: number
    overall_feedback: string | null; per_question: QuestionResult[]
  } | null
}

interface AssignmentDetail {
  questions: { ordering: number; prompt: string; difficulty: string; expected_answer: string | null }[]
  submissions: SubmissionDetail[]
}

const DIFF_COLOR: Record<string, string> = {
  easy: 'bg-green-100 text-green-700', medium: 'bg-amber-100 text-amber-700', hard: 'bg-red-100 text-red-700'
}
const STATUS_COLOR: Record<string, string> = {
  correct: 'text-green-600', wrong: 'text-red-500', partial: 'text-amber-500', skipped: 'text-gray-400'
}
const STATUS_LABEL: Record<string, string> = {
  correct: '✓ Correct', wrong: '✗ Wrong', partial: '½ Partial', skipped: '— Skipped'
}

export default function ParentDashboard() {
  const { user, isParent } = useAuthStore()
  const navigate = useNavigate()
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [details, setDetails] = useState<Record<number, AssignmentDetail>>({})
  const [loadingDetail, setLoadingDetail] = useState<number | null>(null)
  const [expandedSub, setExpandedSub] = useState<number | null>(null)

  useEffect(() => {
    if (!isParent()) { navigate('/parent/login'); return }
    api.get('/assignments').then((r) => setAssignments(r.data)).finally(() => setLoading(false))
  }, [isParent, navigate])

  const loadDetail = async (id: number) => {
    if (details[id]) return
    setLoadingDetail(id)
    try {
      const r = await api.get(`/evaluations/assignment/${id}/submissions`)
      setDetails((prev) => ({ ...prev, [id]: r.data }))
    } finally { setLoadingDetail(null) }
  }

  const toggleExpand = async (id: number) => {
    if (expanded === id) { setExpanded(null); return }
    setExpanded(id)
    await loadDetail(id)
  }

  if (loading) return <Layout title="Dashboard"><LoadingSpinner /></Layout>

  const activeAssignments = assignments.filter((a) => a.status === 'active')
  const selfAssigned = assignments.filter((a) => a.is_self_assigned)

  return (
    <Layout title="Dashboard">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Welcome back, {user?.display_name} 👋</h1>
        <p className="text-gray-500 mt-1">Review assignments and your child's progress.</p>
      </div>

      {/* Quick actions */}
      <div className="grid sm:grid-cols-2 gap-4 mb-8">
        <Link to="/parent/textbooks" className="card hover:shadow-md transition-shadow flex items-center gap-4">
          <div className="w-12 h-12 bg-primary-50 rounded-xl flex items-center justify-center"><BookOpen className="text-primary-500" size={24} /></div>
          <div><div className="font-semibold">Textbook Library</div><div className="text-sm text-gray-500">Upload & manage textbooks</div></div>
        </Link>
        <Link to="/parent/assignments/new" className="card hover:shadow-md transition-shadow flex items-center gap-4">
          <div className="w-12 h-12 bg-amber-50 rounded-xl flex items-center justify-center"><Plus className="text-amber-600" size={24} /></div>
          <div><div className="font-semibold">New Assignment</div><div className="text-sm text-gray-500">Create a practice set</div></div>
        </Link>
      </div>

      {/* FIX #3: Self-assigned notice */}
      {selfAssigned.length > 0 && (
        <div className="bg-purple-50 border border-purple-100 rounded-xl p-3 mb-6 flex items-center gap-2 text-sm text-purple-700">
          <User size={16} />
          <span>Your child has created <strong>{selfAssigned.length}</strong> self-practice session{selfAssigned.length !== 1 ? 's' : ''}.</span>
        </div>
      )}

      {/* FIX #2: Assignments with full detail */}
      <h2 className="text-lg font-semibold text-gray-700 mb-3">All Assignments</h2>
      {activeAssignments.length === 0 ? (
        <div className="card text-center text-gray-400 py-10">
          No assignments yet. <Link to="/parent/assignments/new" className="text-primary-500 font-medium">Create one →</Link>
        </div>
      ) : (
        <div className="space-y-3">
          {assignments.map((a) => (
            <div key={a.id} className="card p-0 overflow-hidden">
              {/* Header */}
              <div className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50"
                onClick={() => toggleExpand(a.id)}>
                <div className="flex items-center gap-3">
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center text-lg ${a.is_self_assigned ? 'bg-purple-50' : 'bg-primary-50'}`}>
                    {a.is_self_assigned ? '💡' : '📝'}
                  </div>
                  <div>
                    <div className="font-semibold text-gray-800">
                      {a.title || `Assignment #${a.id}`}
                      {a.is_self_assigned && <span className="ml-2 text-xs bg-purple-100 text-purple-600 px-2 py-0.5 rounded-full">Self</span>}
                    </div>
                    <div className="text-sm text-gray-500">{a.question_count} questions · {a.status}</div>
                  </div>
                </div>
                {loadingDetail === a.id
                  ? <div className="w-4 h-4 border-2 border-primary-300 border-t-primary-600 rounded-full animate-spin" />
                  : expanded === a.id ? <ChevronDown size={18} className="text-gray-400" /> : <ChevronRight size={18} className="text-gray-400" />
                }
              </div>

              {/* FIX #2: Expanded detail */}
              {expanded === a.id && details[a.id] && (
                <div className="border-t border-gray-100 bg-gray-50">
                  {/* Questions list */}
                  <div className="p-4 border-b border-gray-100">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Questions</p>
                    <div className="space-y-2">
                      {details[a.id].questions.map((q, i) => (
                        <div key={i} className="bg-white rounded-xl p-3 flex items-start gap-2">
                          <span className="text-xs font-bold text-gray-400 shrink-0 mt-0.5">Q{i+1}</span>
                          <div className="flex-1">
                            <p className="text-sm text-gray-800">{q.prompt}</p>
                            {q.expected_answer && (
                              <p className="text-xs text-green-600 mt-1">Answer: {q.expected_answer}</p>
                            )}
                          </div>
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${DIFF_COLOR[q.difficulty] || 'bg-gray-100 text-gray-500'}`}>{q.difficulty}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Submissions */}
                  <div className="p-4">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                      Submissions ({details[a.id].submissions.length})
                    </p>
                    {details[a.id].submissions.length === 0 ? (
                      <p className="text-sm text-gray-400 text-center py-4">No submissions yet.</p>
                    ) : (
                      <div className="space-y-2">
                        {details[a.id].submissions.map((sub) => (
                          <div key={sub.id} className="bg-white rounded-xl overflow-hidden border border-gray-100">
                            {/* Submission header */}
                            <div className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-50"
                              onClick={() => setExpandedSub(expandedSub === sub.id ? null : sub.id)}>
                              <div className="flex items-center gap-2">
                                {sub.processing_status === 'done' && sub.evaluation
                                  ? <CheckCircle2 size={16} className="text-green-500" />
                                  : sub.processing_status === 'error'
                                  ? <AlertCircle size={16} className="text-red-400" />
                                  : <Clock size={16} className="text-amber-400" />}
                                <span className="text-sm font-medium text-gray-700">Attempt {sub.attempt_number}</span>
                                <span className="text-xs text-gray-400">{new Date(sub.submitted_at).toLocaleString()}</span>
                              </div>
                              <div className="flex items-center gap-2">
                                {sub.evaluation && (
                                  <span className={`text-sm font-bold ${sub.evaluation.score_percent >= 70 ? 'text-green-600' : 'text-red-500'}`}>
                                    {sub.evaluation.score_percent}%
                                  </span>
                                )}
                                {expandedSub === sub.id ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
                              </div>
                            </div>

                            {/* Per-question results */}
                            {expandedSub === sub.id && sub.evaluation && (
                              <div className="border-t border-gray-100 p-3 space-y-2">
                                {sub.evaluation.per_question.map((qr, qi) => (
                                  <div key={qi} className="text-sm flex items-start gap-2 py-1 border-b border-gray-50 last:border-0">
                                    <span className="text-gray-400 font-medium shrink-0 w-6">Q{qi+1}</span>
                                    <div className="flex-1 min-w-0">
                                      {qr.question_prompt && <p className="text-gray-700 text-xs mb-1">{qr.question_prompt}</p>}
                                      {qr.ocr_text && <p className="text-gray-500 text-xs font-mono truncate">Answer: {qr.ocr_text}</p>}
                                      {qr.feedback && <p className="text-gray-500 text-xs mt-0.5 italic">{qr.feedback}</p>}
                                    </div>
                                    <span className={`text-xs font-semibold shrink-0 ${STATUS_COLOR[qr.status] || 'text-gray-400'}`}>
                                      {STATUS_LABEL[qr.status] || qr.status}
                                    </span>
                                  </div>
                                ))}
                                {sub.evaluation.overall_feedback && (
                                  <p className="text-xs text-gray-500 italic pt-1">{sub.evaluation.overall_feedback}</p>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Layout>
  )
}
