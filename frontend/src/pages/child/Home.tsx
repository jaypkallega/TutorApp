import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import Layout from '../../components/Layout'
import LoadingSpinner from '../../components/LoadingSpinner'
import api from '../../api/client'
import { BookOpen, PlayCircle, CheckCircle2, PlusCircle, Star, Sparkles, Trophy } from 'lucide-react'

interface Assignment { id: number; title: string | null; question_count: number; status: string; is_self_assigned: boolean }
interface Chapter { id: number; chapter_number: number; title: string; approved: boolean; textbook_title?: string }
interface ProgressItem { concept_id: number; concept_name: string; chapter_title: string; mastery_level: string; unlocked_for_test: boolean }

const MASTERY = {
  not_started: { icon: '○', color: 'text-gray-300', bg: 'bg-gray-50', label: 'Not started' },
  introduced:  { icon: '◑', color: 'text-blue-500', bg: 'bg-blue-50', label: 'Introduced' },
  practised:   { icon: '◕', color: 'text-amber-500', bg: 'bg-amber-50', label: 'Practised' },
  mastered:    { icon: '●', color: 'text-green-500', bg: 'bg-green-50', label: 'Mastered' },
}

export default function ChildHome() {
  const { user, setUser } = useAuthStore()
  const navigate = useNavigate()
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [progressItems, setProgressItems] = useState<ProgressItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const init = async () => {
      if (!user || user.role !== 'child') {
        try { const r = await api.post('/auth/child/session'); setUser(r.data) }
        catch { navigate('/parent/login'); return }
      }
      try {
        const [aRes, cRes, pRes] = await Promise.all([
          api.get('/assignments'),
          api.get('/chapters'),
          api.get('/teach/progress').catch(() => ({ data: [] })),
        ])
        setAssignments(aRes.data)
        setChapters(cRes.data.filter((c: Chapter) => c.approved))
        setProgressItems(pRes.data)
      } finally { setLoading(false) }
    }
    init()
  }, [])

  if (loading) return <Layout><LoadingSpinner text="Loading your work..." /></Layout>

  const parentAssignments = assignments.filter(a => a.status === 'active' && !a.is_self_assigned)
  const selfAssignments = assignments.filter(a => a.status === 'active' && a.is_self_assigned)
  const masteredCount = progressItems.filter(p => p.mastery_level === 'mastered').length
  const inProgressCount = progressItems.filter(p => ['introduced', 'practised'].includes(p.mastery_level)).length

  return (
    <Layout>
      {/* Greeting */}
      <div className="text-center py-4 mb-4">
        <div className="text-4xl mb-2">👋</div>
        <h1 className="text-2xl font-bold text-gray-800">Hi, {user?.display_name}!</h1>
        {masteredCount > 0 && (
          <div className="flex items-center justify-center gap-2 mt-2">
            <Trophy size={16} className="text-amber-400" />
            <span className="text-sm text-gray-500">{masteredCount} concept{masteredCount !== 1 ? 's' : ''} mastered</span>
            {inProgressCount > 0 && <span className="text-sm text-gray-400">· {inProgressCount} in progress</span>}
          </div>
        )}
      </div>

      {/* Parent assignments */}
      <section className="mb-6">
        <h2 className="text-base font-semibold text-gray-700 mb-3 flex items-center gap-2">
          <Star className="text-amber-400" size={18} /> Assigned by Parent
        </h2>
        {parentAssignments.length === 0 ? (
          <div className="card text-center py-6">
            <CheckCircle2 size={32} className="mx-auto mb-2 text-green-400" />
            <p className="text-gray-500 text-sm">No pending assignments.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {parentAssignments.map((a) => (
              <div key={a.id} className="card flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-primary-50 rounded-xl flex items-center justify-center text-xl shrink-0">📝</div>
                  <div>
                    <div className="font-semibold text-gray-800 text-sm">{a.title || `Practice Set #${a.id}`}</div>
                    <div className="text-xs text-gray-500">{a.question_count} question{a.question_count !== 1 ? 's' : ''}</div>
                  </div>
                </div>
                <Link to={`/child/solve/${a.id}`} className="btn-primary text-sm flex items-center gap-1 py-2 px-4">
                  <PlayCircle size={16} /> Start
                </Link>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* AI Learn with tutor */}
      {chapters.length > 0 && (
        <section className="mb-6">
          <h2 className="text-base font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <Sparkles className="text-primary-500" size={18} /> Learn with AI Tutor
          </h2>
          <div className="grid sm:grid-cols-2 gap-3">
            {chapters.map((ch) => {
              // Count mastery for concepts in this chapter
              const chapterProgress = progressItems.filter(p => p.chapter_title === ch.title)
              const masteredInChapter = chapterProgress.filter(p => p.mastery_level === 'mastered').length
              const totalInChapter = chapterProgress.length
              return (
                <Link key={ch.id} to={`/child/teach/${ch.id}`}
                  className="card hover:shadow-md transition-all flex items-center gap-3 cursor-pointer">
                  <div className="w-10 h-10 bg-primary-50 rounded-xl flex items-center justify-center font-bold text-primary-600 shrink-0 text-sm">
                    {ch.chapter_number}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-800 truncate text-sm">{ch.title}</div>
                    {ch.textbook_title && <div className="text-xs text-gray-400 truncate">{ch.textbook_title}</div>}
                    {totalInChapter > 0 && (
                      <div className="text-xs text-primary-500 mt-0.5">{masteredInChapter}/{totalInChapter} mastered</div>
                    )}
                  </div>
                  <Sparkles size={16} className="text-primary-300 shrink-0" />
                </Link>
              )
            })}
          </div>
        </section>
      )}

      {/* Self-practice */}
      <section className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-gray-700 flex items-center gap-2">
            <PlusCircle className="text-purple-500" size={18} /> My Practice
          </h2>
          {chapters.length > 0 && (
            <Link to="/child/self-assign" className="text-xs text-primary-500 font-medium">+ Create new</Link>
          )}
        </div>
        {selfAssignments.length === 0 ? (
          <div className="card text-center py-6 border-dashed border-2 border-gray-100">
            <PlusCircle size={24} className="mx-auto mb-2 text-gray-300" />
            <p className="text-gray-400 text-sm">No self-practice sessions yet.</p>
            {chapters.length > 0 && (
              <Link to="/child/self-assign" className="text-primary-500 text-sm font-medium mt-1 block">Create your own →</Link>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {selfAssignments.map((a) => (
              <div key={a.id} className="card flex items-center justify-between border-l-4 border-purple-200">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-purple-50 rounded-xl flex items-center justify-center text-xl shrink-0">💡</div>
                  <div>
                    <div className="font-semibold text-gray-800 text-sm">{a.title || `My Practice #${a.id}`}</div>
                    <div className="text-xs text-gray-500">{a.question_count} questions · Self-assigned</div>
                  </div>
                </div>
                <Link to={`/child/solve/${a.id}`} className="text-sm bg-purple-600 text-white px-4 py-2 rounded-xl flex items-center gap-1 hover:bg-purple-700">
                  <PlayCircle size={16} /> Start
                </Link>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="text-center mt-4">
        <Link to="/parent/login" className="text-xs text-gray-400 hover:text-gray-600">Parent login →</Link>
      </div>
    </Layout>
  )
}
