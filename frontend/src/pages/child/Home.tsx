import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import Layout from '../../components/Layout'
import LoadingSpinner from '../../components/LoadingSpinner'
import api from '../../api/client'
import { BookOpen, PlayCircle, CheckCircle2, PlusCircle, Star, Sparkles, Trophy, ChevronRight } from 'lucide-react'

interface Assignment  { id: number; title: string | null; question_count: number; status: string; is_self_assigned: boolean }
interface Chapter     { id: number; chapter_number: number; title: string; approved: boolean; textbook_title?: string; textbook_id?: number }
interface ProgressItem {
  concept_id: number; concept_name: string
  chapter_title: string; chapter_id: number
  mastery_level: string; unlocked_for_test: boolean
  last_interaction: string | null
}

// ── mastery colour tokens ─────────────────────────────────────────────────────
const MASTERY_BAR: Record<string, string> = {
  not_started: 'bg-gray-200',
  introduced:  'bg-blue-400',
  practised:   'bg-amber-400',
  mastered:    'bg-green-500',
}

// ── Chapter chip component ────────────────────────────────────────────────────
function ChapterChip({
  ch, mastered, total, isContinue,
}: {
  ch: Chapter; mastered: number; total: number; isContinue: boolean
}) {
  const pct = total > 0 ? Math.round((mastered / total) * 100) : 0
  const allDone = total > 0 && mastered === total
  const hasProgress = total > 0

  return (
    <Link
      id={`chapter-chip-${ch.id}`}
      to={`/child/teach/${ch.id}`}
      className={`
        flex-none w-44 min-h-[96px] rounded-2xl border-2 p-3 flex flex-col gap-1 transition-all
        hover:shadow-md hover:-translate-y-0.5 active:scale-95
        ${isContinue
          ? 'border-teal-400 bg-gradient-to-br from-teal-50 to-white'
          : allDone
          ? 'border-green-200 bg-green-50'
          : hasProgress
          ? 'border-primary-200 bg-white'
          : 'border-gray-100 bg-white hover:border-primary-200'}
      `}
    >
      {/* Top row: chapter badge + continue pill */}
      <div className="flex items-center justify-between gap-1">
        <span className={`
          text-xs font-bold px-1.5 py-0.5 rounded-lg leading-none
          ${isContinue ? 'bg-teal-500 text-white' : 'bg-primary-100 text-primary-700'}
        `}>
          Ch.{ch.chapter_number}
        </span>
        {isContinue && (
          <span className="text-[10px] font-semibold text-teal-600 flex items-center gap-0.5 whitespace-nowrap">
            Continue <ChevronRight size={10} />
          </span>
        )}
        {allDone && !isContinue && (
          <CheckCircle2 size={13} className="text-green-500 shrink-0" />
        )}
      </div>

      {/* Title */}
      <p className="text-xs font-semibold text-gray-800 leading-tight line-clamp-2 flex-1">
        {ch.title}
      </p>

      {/* Progress bar */}
      {hasProgress ? (
        <div className="mt-auto">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-gray-400">{mastered}/{total} mastered</span>
            <span className="text-[10px] font-medium text-gray-500">{pct}%</span>
          </div>
          <div className="h-1 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${MASTERY_BAR.mastered}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      ) : (
        <p className="text-[10px] text-gray-400 mt-auto">Tap to start ✨</p>
      )}
    </Link>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ChildHome() {
  const { user, setUser } = useAuthStore()
  const navigate = useNavigate()
  const [assignments,   setAssignments]   = useState<Assignment[]>([])
  const [chapters,      setChapters]      = useState<Chapter[]>([])
  const [progressItems, setProgressItems] = useState<ProgressItem[]>([])
  const [loading,       setLoading]       = useState(true)

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

  // ── Derived values ──────────────────────────────────────────────────────────
  const parentAssignments = assignments.filter(a => a.status === 'active' && !a.is_self_assigned)
  const selfAssignments   = assignments.filter(a => a.status === 'active' && a.is_self_assigned)
  const masteredCount     = progressItems.filter(p => p.mastery_level === 'mastered').length
  const inProgressCount   = progressItems.filter(p => ['introduced', 'practised'].includes(p.mastery_level)).length

  // Last-accessed chapter: concept with the most-recent last_interaction
  const lastChapterId = useMemo(() => {
    const withTime = progressItems.filter(p => p.last_interaction && p.chapter_id)
    if (!withTime.length) return null
    const latest = withTime.reduce((a, b) =>
      new Date(a.last_interaction!) > new Date(b.last_interaction!) ? a : b
    )
    return latest.chapter_id
  }, [progressItems])

  // Group chapters by textbook (preserve insertion order)
  const bookGroups = useMemo(() => {
    const groups: Record<string, { textbook_id?: number; chapters: Chapter[] }> = {}
    for (const ch of chapters) {
      const key = ch.textbook_title || 'My Textbook'
      if (!groups[key]) groups[key] = { textbook_id: ch.textbook_id, chapters: [] }
      groups[key].chapters.push(ch)
    }
    return groups
  }, [chapters])

  const multipleBooks = Object.keys(bookGroups).length > 1

  if (loading) return <Layout><LoadingSpinner text="Loading your work..." /></Layout>

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

      {/* ── Learn with AI Tutor — horizontal strip, grouped by textbook ── */}
      {chapters.length > 0 && (
        <section className="mb-6">
          <h2 className="text-base font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <Sparkles className="text-primary-500" size={18} /> Learn with AI Tutor
          </h2>

          <div className="space-y-4">
            {Object.entries(bookGroups).map(([bookTitle, { chapters: bookChapters }]) => (
              <div key={bookTitle}>
                {/* Textbook label — only shown when multiple books */}
                {multipleBooks && (
                  <div className="flex items-center gap-1.5 mb-2">
                    <BookOpen size={12} className="text-gray-400" />
                    <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider truncate">
                      {bookTitle}
                    </span>
                  </div>
                )}

                {/* Horizontal chip strip */}
                <div className="flex gap-3 overflow-x-auto scrollbar-hide pb-2 -mx-4 px-4">
                  {bookChapters.map((ch) => {
                    const chapterProgress = progressItems.filter(p => p.chapter_id === ch.id)
                    const mastered = chapterProgress.filter(p => p.mastery_level === 'mastered').length
                    const total    = chapterProgress.length
                    return (
                      <ChapterChip
                        key={ch.id}
                        ch={ch}
                        mastered={mastered}
                        total={total}
                        isContinue={ch.id === lastChapterId}
                      />
                    )
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Scroll hint — only shown when there are enough chips to scroll */}
          {chapters.length > 3 && (
            <p className="text-[10px] text-gray-400 mt-1 text-right flex items-center justify-end gap-0.5">
              Swipe to see more <ChevronRight size={10} />
            </p>
          )}
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
