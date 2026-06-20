import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import Layout from '../../components/Layout'
import LoadingSpinner from '../../components/LoadingSpinner'
import api from '../../api/client'
import { Plus, Wand2, CheckSquare, Square, ChevronDown, ChevronRight } from 'lucide-react'

interface Chapter {
  id: number; chapter_number: number; title: string
  approved: boolean; textbook_id: number
  textbook_title: string; textbook_subject: string
}
interface Exercise {
  id: number; prompt: string; difficulty: string
  exercise_type: string | null; source: string
}

const DIFF_COLOR: Record<string, string> = {
  easy: 'bg-green-100 text-green-700',
  medium: 'bg-amber-100 text-amber-700',
  hard: 'bg-red-100 text-red-700',
}

export default function AssignmentBuilder() {
  const { isParent } = useAuthStore()
  const navigate = useNavigate()
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [selectedChapters, setSelectedChapters] = useState<Set<number>>(new Set())
  const [exercises, setExercises] = useState<Exercise[]>([])
  // Map from exercise id -> chapter id (for grouping in the UI)
  const [exerciseChapterMap, setExerciseChapterMap] = useState<Record<number, number>>({})
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(true)
  const [loadingExercises, setLoadingExercises] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [genForm, setGenForm] = useState({ count: 5, difficulty: 'medium' })
  const [assignForm, setAssignForm] = useState({
    title: '', explanation_policy: 'after_attempt', show_wrong_reasons: true,
  })
  const [collapsedBooks, setCollapsedBooks] = useState<Set<number>>(new Set())
  // Adaptive difficulty: recommendation for most-recently clicked chapter
  const [lastClickedChapter, setLastClickedChapter] = useState<number | null>(null)
  const [difficultyRec, setDifficultyRec] = useState<{
    recommended_difficulty: string; has_data: boolean;
    reason: string | null;
    cautions: string[];
    signals: { avg_accuracy: number | null; avg_hints_per_q: number | null;
               stability: number | null; readiness: number | null }
  } | null>(null)

  useEffect(() => {
    if (!isParent()) { navigate('/parent/login'); return }
    api.get('/chapters').then((r) => {
      const approved = r.data.filter((c: Chapter) => c.approved)
      setChapters(approved)
    }).finally(() => setLoading(false))
  }, [isParent, navigate])

  // Fix 2: group chapters by textbook
  const bookGroups = chapters.reduce((acc, ch) => {
    const key = ch.textbook_id
    if (!acc[key]) acc[key] = { title: ch.textbook_title, subject: ch.textbook_subject, chapters: [] }
    acc[key].chapters.push(ch)
    return acc
  }, {} as Record<number, { title: string; subject: string; chapters: Chapter[] }>)

  const selectChapter = async (id: number) => {
    // Toggle chapter in/out of selection set
    setSelectedChapters((prev) => {
      const next = new Set(prev)
      if (next.has(id)) { next.delete(id) } else { next.add(id) }
      return next
    })
    setLastClickedChapter(id)
    setDifficultyRec(null)
    // Load difficulty rec for this chapter
    api.get(`/chapters/${id}/difficulty-recommendation`).then((r) => {
      if (r.data) setDifficultyRec(r.data)
    }).catch(() => null)
  }

  // Fetch exercises whenever the selected chapters set changes
  useEffect(() => {
    if (selectedChapters.size === 0) { setExercises([]); setExerciseChapterMap({}); setSelectedIds(new Set()); return }
    setLoadingExercises(true)
    const ids = Array.from(selectedChapters)
    Promise.all(ids.map((cid) => api.get(`/exercises?chapter_id=${cid}`).then((r) => ({ cid, exs: r.data as Exercise[] }))))
      .then((results) => {
        const allExercises: Exercise[] = []
        const chMap: Record<number, number> = {}
        for (const { cid, exs } of results) {
          for (const ex of exs) { allExercises.push(ex); chMap[ex.id] = cid }
        }
        setExercises(allExercises)
        setExerciseChapterMap(chMap)
        setSelectedIds(new Set())
      })
      .finally(() => setLoadingExercises(false))
  }, [selectedChapters])

  const generateMore = async () => {
    if (selectedChapters.size === 0) return
    // Generate for the last-clicked chapter
    const chId = lastClickedChapter ?? Array.from(selectedChapters)[0]
    setGenerating(true)
    try {
      const r = await api.post('/exercises/generate', {
        chapter_id: chId, count: genForm.count, difficulty: genForm.difficulty,
      })
      const newExs: Exercise[] = r.data
      setExercises((prev) => [...prev, ...newExs])
      setExerciseChapterMap((prev) => {
        const next = { ...prev }
        for (const ex of newExs) next[ex.id] = chId
        return next
      })
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Generation failed. Check LLM settings.')
    } finally { setGenerating(false) }
  }

  const toggleSelect = (id: number) => setSelectedIds((prev) => {
    const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next
  })

  const createAssignment = async () => {
    if (selectedIds.size === 0) { alert('Select at least one question'); return }
    if (selectedChapters.size === 0) return
    // Use the first selected chapter as the primary chapter_id for the assignment
    const primaryChapterId = lastClickedChapter ?? Array.from(selectedChapters)[0]
    setSaving(true)
    try {
      await api.post('/assignments', {
        chapter_id: primaryChapterId,
        title: assignForm.title || undefined,
        exercise_ids: Array.from(selectedIds),
        explanation_policy: assignForm.explanation_policy,
        show_wrong_reasons: assignForm.show_wrong_reasons,
      })
      navigate('/parent/dashboard')
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to create assignment')
    } finally { setSaving(false) }
  }

  const toggleBookCollapse = (tbId: number) => setCollapsedBooks((prev) => {
    const next = new Set(prev); next.has(tbId) ? next.delete(tbId) : next.add(tbId); return next
  })

  if (loading) return <Layout title="New Assignment"><LoadingSpinner /></Layout>

  const selectedChaptersArr = Array.from(selectedChapters)
    .map((id) => chapters.find((c) => c.id === id))
    .filter(Boolean) as Chapter[]

  return (
    <Layout title="New Assignment">
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Left: question pool */}
        <div className="lg:col-span-2 space-y-4">

          {/* Step 1: Choose chapter — grouped by textbook */}
          <div className="card">
            <h2 className="font-semibold mb-3 text-gray-800">1. Choose Chapter</h2>
            {Object.keys(bookGroups).length === 0 ? (
              <p className="text-gray-500 text-sm">No approved chapters yet.{' '}
                <a href="/parent/textbooks" className="text-primary-500 font-medium">Upload a textbook →</a>
              </p>
            ) : (
              <div className="space-y-3">
                {Object.entries(bookGroups).map(([tbId, group]) => {
                  const id = Number(tbId)
                  const collapsed = collapsedBooks.has(id)
                  return (
                    <div key={id} className="border border-gray-100 rounded-xl overflow-hidden">
                      {/* Book header */}
                      <button
                        onClick={() => toggleBookCollapse(id)}
                        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-all text-left"
                      >
                        <div>
                          <span className="font-semibold text-gray-700 text-sm">{group.title}</span>
                          {group.subject && (
                            <span className="ml-2 text-xs bg-primary-50 text-primary-600 px-2 py-0.5 rounded-full">{group.subject}</span>
                          )}
                          <span className="ml-2 text-xs text-gray-400">{group.chapters.length} chapter{group.chapters.length !== 1 ? 's' : ''}</span>
                        </div>
                        {collapsed ? <ChevronRight size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
                      </button>
                      {/* Chapters */}
                      {!collapsed && (
                        <div className="p-3 grid sm:grid-cols-2 gap-2">
                          {group.chapters.map((ch) => (
                            <button
                              key={ch.id}
                              onClick={() => selectChapter(ch.id)}
                              className={`text-left p-3 rounded-xl border-2 text-sm font-medium transition-all ${
                                selectedChapters.has(ch.id)
                                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                                  : 'border-gray-100 hover:border-gray-200 text-gray-700'
                              }`}
                            >
                              <span>Ch. {ch.chapter_number}: {ch.title}</span>
                              {selectedChapters.has(ch.id) && difficultyRec?.has_data && lastClickedChapter === ch.id && difficultyRec.recommended_difficulty !== 'easy' && (
                                <span className="ml-1.5 text-xs bg-teal-100 text-teal-700 px-1.5 py-0.5 rounded-full font-medium">
                                  ⬆️ {difficultyRec.recommended_difficulty} ready
                                </span>
                              )}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Adaptive difficulty recommendation panel */}
          {selectedChapters.size > 0 && difficultyRec?.has_data && (
            <div className="card bg-teal-50 border border-teal-100 p-4 mb-0">
              <div className="flex items-start gap-3">
                <span className="text-xl shrink-0">📊</span>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-teal-800">
                    Suggested difficulty: <span className="capitalize">{difficultyRec.recommended_difficulty}</span>
                  </p>
                  {difficultyRec.reason && (
                    <p className="text-xs text-teal-700 mt-0.5">{difficultyRec.reason}</p>
                  )}
                  {difficultyRec.cautions.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {difficultyRec.cautions.map((c, i) => (
                        <p key={i} className="text-xs text-amber-700 flex items-start gap-1">
                          <span className="shrink-0">⚠️</span>{c}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Questions */}
          {selectedChapters.size > 0 && (
            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h2 className="font-semibold text-gray-800">2. Pick Questions ({selectedIds.size} selected)</h2>
                  {selectedChaptersArr.length > 0 && (
                    <p className="text-xs text-gray-400 mt-0.5">
                      {selectedChaptersArr.map((c) => `Ch. ${c.chapter_number}: ${c.title}`).join('  ·  ')}
                    </p>
                  )}
                </div>
                <div className="flex gap-2 text-sm">
                  <button onClick={() => setSelectedIds(new Set(exercises.map(e => e.id)))} className="text-primary-500 font-medium">All</button>
                  <span className="text-gray-300">|</span>
                  <button onClick={() => setSelectedIds(new Set())} className="text-gray-500">None</button>
                </div>
              </div>

              {/* Generate — targets last-clicked chapter */}
              <div className="bg-amber-50 rounded-xl p-3 mb-4 flex flex-wrap items-center gap-2">
                <Wand2 size={16} className="text-amber-600" />
                <span className="text-sm text-amber-700 font-medium">Generate AI questions
                  {lastClickedChapter && selectedChapters.size > 1 && (
                    <span className="font-normal text-amber-600"> (for last-selected chapter)</span>
                  )}:
                </span>
                <select className="text-sm border-0 bg-white rounded-lg px-2 py-1" value={genForm.count}
                  onChange={(e) => setGenForm({ ...genForm, count: +e.target.value })}>
                  {[3, 5, 8, 10].map(n => <option key={n} value={n}>{n}</option>)}
                </select>
                <select className="text-sm border-0 bg-white rounded-lg px-2 py-1" value={genForm.difficulty}
                  onChange={(e) => setGenForm({ ...genForm, difficulty: e.target.value })}>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
                <button onClick={generateMore} disabled={generating}
                  className="bg-amber-500 text-white text-sm px-3 py-1.5 rounded-lg font-medium hover:bg-amber-600 disabled:opacity-50">
                  {generating ? 'Generating...' : 'Generate'}
                </button>
              </div>

              {loadingExercises ? <LoadingSpinner text="Loading questions…" /> : exercises.length === 0 ? (
                <p className="text-gray-400 text-sm text-center py-6">No questions yet. Generate some above.</p>
              ) : (
                <div className="space-y-4 max-h-[500px] overflow-y-auto">
                  {/* Group questions by chapter */}
                  {selectedChaptersArr.map((ch) => {
                    const chExercises = exercises.filter((ex) => exerciseChapterMap[ex.id] === ch.id)
                    if (chExercises.length === 0) return null
                    return (
                      <div key={ch.id}>
                        {selectedChapters.size > 1 && (
                          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 sticky top-0 bg-white py-1">
                            Ch. {ch.chapter_number}: {ch.title}
                          </p>
                        )}
                        <div className="space-y-2">
                          {chExercises.map((ex) => (
                            <div key={ex.id} onClick={() => toggleSelect(ex.id)}
                              className={`flex items-start gap-3 p-3 rounded-xl cursor-pointer transition-all border-2 ${
                                selectedIds.has(ex.id) ? 'border-primary-400 bg-primary-50' : 'border-transparent bg-gray-50 hover:bg-gray-100'}`}>
                              <div className="mt-0.5 text-primary-500 shrink-0">
                                {selectedIds.has(ex.id) ? <CheckSquare size={18} /> : <Square size={18} className="text-gray-300" />}
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm text-gray-800 line-clamp-2">{ex.prompt}</p>
                                <div className="flex gap-2 mt-1">
                                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${DIFF_COLOR[ex.difficulty]}`}>{ex.difficulty}</span>
                                  <span className="text-xs text-gray-400">{ex.source === 'ai_generated' ? '✨ AI' : '📖 Textbook'}</span>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right: settings */}
        <div>
          <div className="card sticky top-24">
            <h2 className="font-semibold mb-4 text-gray-800">3. Settings</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Title (optional)</label>
                <input className="input-field" value={assignForm.title}
                  onChange={(e) => setAssignForm({ ...assignForm, title: e.target.value })}
                  placeholder="e.g. Fractions Practice" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Show Explanations</label>
                <select className="input-field" value={assignForm.explanation_policy}
                  onChange={(e) => setAssignForm({ ...assignForm, explanation_policy: e.target.value })}>
                  <option value="locked">Never</option>
                  <option value="after_attempt">After submitting</option>
                  <option value="always">Always</option>
                </select>
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={assignForm.show_wrong_reasons}
                  onChange={(e) => setAssignForm({ ...assignForm, show_wrong_reasons: e.target.checked })}
                  className="w-4 h-4 accent-primary-500" />
                <span className="text-sm text-gray-700">Show correct answers in results</span>
              </label>
              <div className="border-t pt-4">
                <div className="text-sm text-gray-500 mb-3">{selectedIds.size} question{selectedIds.size !== 1 ? 's' : ''} selected</div>
                <button onClick={createAssignment} disabled={saving || selectedIds.size === 0}
                  className="btn-primary w-full flex items-center justify-center gap-2">
                  <Plus size={18} /> {saving ? 'Creating...' : 'Create Assignment'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  )
}
