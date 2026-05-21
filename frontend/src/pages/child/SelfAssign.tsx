import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import Layout from '../../components/Layout'
import LoadingSpinner from '../../components/LoadingSpinner'
import api from '../../api/client'
import { Plus, CheckSquare, Square, Wand2, ChevronDown, ChevronRight } from 'lucide-react'

interface Chapter {
  id: number; chapter_number: number; title: string
  approved: boolean; textbook_id: number
  textbook_title: string; textbook_subject: string
}
interface Exercise {
  id: number; prompt: string; difficulty: string; source: string
}

const DIFF_COLOR: Record<string, string> = {
  easy: 'bg-green-100 text-green-700',
  medium: 'bg-amber-100 text-amber-700',
  hard: 'bg-red-100 text-red-700',
}

export default function SelfAssign() {
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null)
  const [exercises, setExercises] = useState<Exercise[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(true)
  const [loadingEx, setLoadingEx] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [title, setTitle] = useState('')
  // Fix 2: count + difficulty for generation
  const [genCount, setGenCount] = useState(5)
  const [genDiff, setGenDiff] = useState('medium')
  // Fix 3: collapsible book groups
  const [collapsedBooks, setCollapsedBooks] = useState<Set<number>>(new Set())
  // Adaptive difficulty recommendation for selected chapter
  const [difficultyRec, setDifficultyRec] = useState<{
    recommended_difficulty: string; has_data: boolean;
    reason: string | null; cautions: string[];
  } | null>(null)

  useEffect(() => {
    api.get('/chapters')
      .then((r) => setChapters(r.data.filter((c: Chapter) => c.approved)))
      .finally(() => setLoading(false))
  }, [])

  // Fix 3: group chapters by textbook
  const bookGroups = chapters.reduce((acc, ch) => {
    const key = ch.textbook_id
    if (!acc[key]) acc[key] = { title: ch.textbook_title, subject: ch.textbook_subject, chapters: [] }
    acc[key].chapters.push(ch)
    return acc
  }, {} as Record<number, { title: string; subject: string; chapters: Chapter[] }>)

  const toggleBookCollapse = (tbId: number) => setCollapsedBooks((prev) => {
    const next = new Set(prev); next.has(tbId) ? next.delete(tbId) : next.add(tbId); return next
  })

  const selectChapter = async (id: number) => {
    setSelectedChapter(id)
    setSelectedIds(new Set())
    setDifficultyRec(null)
    setLoadingEx(true)
    try {
      const [exRes, recRes] = await Promise.all([
        api.get(`/exercises?chapter_id=${id}`),
        api.get(`/chapters/${id}/difficulty-recommendation`).catch(() => null),
      ])
      setExercises(exRes.data)
      if (recRes?.data?.has_data) {
        setDifficultyRec(recRes.data)
        setGenDiff(recRes.data.recommended_difficulty)  // auto-default
      }
    } finally { setLoadingEx(false) }
  }

  const generateMore = async () => {
    if (!selectedChapter) return
    setGenerating(true)
    try {
      // Fix 1: child is now allowed to call this endpoint
      const r = await api.post('/exercises/generate', {
        chapter_id: selectedChapter,
        count: genCount,      // Fix 2: use selected count
        difficulty: genDiff,
      })
      // Fix 4: avoid adding duplicate exercises
      setExercises((prev) => {
        const existingIds = new Set(prev.map(e => e.id))
        const newOnes = r.data.filter((e: Exercise) => !existingIds.has(e.id))
        return [...prev, ...newOnes]
      })
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Generation failed. Check LLM settings.')
    } finally { setGenerating(false) }
  }

  const toggle = (id: number) => setSelectedIds((prev) => {
    const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next
  })

  const create = async () => {
    if (selectedIds.size === 0) { alert('Select at least one question'); return }
    if (!selectedChapter) return
    setSaving(true)
    try {
      // Fix 4: deduplicate selectedIds before sending
      const uniqueIds = Array.from(new Set(Array.from(selectedIds)))
      const r = await api.post('/assignments', {
        chapter_id: selectedChapter,
        title: title || `My Practice — ${new Date().toLocaleDateString()}`,
        exercise_ids: uniqueIds,
        explanation_policy: 'after_attempt',
        show_wrong_reasons: true,
        allowed_difficulties: ['easy', 'medium', 'hard'],
      })
      navigate(`/child/solve/${r.data.id}`)
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to create assignment')
    } finally { setSaving(false) }
  }

  if (loading) return <Layout title="Practice Yourself"><LoadingSpinner /></Layout>

  const selectedChapterObj = chapters.find(c => c.id === selectedChapter)

  return (
    <Layout title="Create Your Own Practice">
      <div className="mb-4">
        <h1 className="text-xl font-bold text-gray-800">Create Your Own Practice 📚</h1>
        <p className="text-gray-500 text-sm mt-1">Pick a topic and choose questions to practise on your own.</p>
      </div>

      {/* Step 1: Chapter — Fix 3: grouped by book */}
      <div className="card mb-4">
        <h2 className="font-semibold mb-3 text-gray-700">1. Pick a Topic</h2>
        {Object.keys(bookGroups).length === 0 ? (
          <p className="text-gray-400 text-sm">No topics available yet. Ask your parent to upload a textbook.</p>
        ) : (
          <div className="space-y-3">
            {Object.entries(bookGroups).map(([tbId, group]) => {
              const id = Number(tbId)
              const collapsed = collapsedBooks.has(id)
              return (
                <div key={id} className="border border-gray-100 rounded-xl overflow-hidden">
                  <button onClick={() => toggleBookCollapse(id)}
                    className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 text-left transition-all">
                    <div>
                      <span className="font-semibold text-gray-700 text-sm">{group.title}</span>
                      {group.subject && (
                        <span className="ml-2 text-xs bg-primary-50 text-primary-600 px-2 py-0.5 rounded-full">{group.subject}</span>
                      )}
                      <span className="ml-2 text-xs text-gray-400">{group.chapters.length} chapter{group.chapters.length !== 1 ? 's' : ''}</span>
                    </div>
                    {collapsed ? <ChevronRight size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
                  </button>
                  {!collapsed && (
                    <div className="p-3 grid sm:grid-cols-2 gap-2">
                      {group.chapters.map((ch) => (
                        <button key={ch.id} onClick={() => selectChapter(ch.id)}
                          className={`text-left p-3 rounded-xl border-2 text-sm font-medium transition-all ${
                            selectedChapter === ch.id
                              ? 'border-primary-500 bg-primary-50 text-primary-700'
                              : 'border-gray-100 hover:border-gray-200 text-gray-700'}`}>
                          Ch. {ch.chapter_number}: {ch.title}
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

      {/* Step 2: Questions */}
      {selectedChapter && (
        <div className="card mb-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="font-semibold text-gray-700">2. Choose Questions ({selectedIds.size} selected)</h2>
              {selectedChapterObj && (
                <p className="text-xs text-gray-400 mt-0.5">
                  {selectedChapterObj.textbook_title} · Ch. {selectedChapterObj.chapter_number}
                </p>
              )}
            </div>
            <div className="flex gap-2 text-sm">
              <button onClick={() => setSelectedIds(new Set(exercises.map(e => e.id)))} className="text-primary-500 font-medium">All</button>
              <span className="text-gray-300">|</span>
              <button onClick={() => setSelectedIds(new Set())} className="text-gray-500">None</button>
            </div>
          </div>

          {/* Fix 1 + 2: Generate with count selector — now works for child role */}
          <div className="bg-amber-50 rounded-xl p-3 mb-3 flex flex-wrap items-center gap-2">
            <Wand2 size={16} className="text-amber-600 shrink-0" />
            <span className="text-sm text-amber-700 font-medium">Generate questions:</span>
            {/* Fix 2: count dropdown */}
            <select className="text-sm border-0 bg-white rounded-lg px-2 py-1 shadow-sm"
              value={genCount} onChange={(e) => setGenCount(+e.target.value)}>
              {[3, 5, 8, 10, 15].map(n => <option key={n} value={n}>{n} questions</option>)}
            </select>
            <select className="text-sm border-0 bg-white rounded-lg px-2 py-1 shadow-sm"
              value={genDiff} onChange={(e) => setGenDiff(e.target.value)}>
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
            {difficultyRec?.has_data && (
              <div className="w-full mt-2 space-y-1">
                {difficultyRec.reason && (
                  <p className="text-xs text-teal-700">
                    {difficultyRec.recommended_difficulty === 'easy' ? '🟢' :
                     difficultyRec.recommended_difficulty === 'medium' ? '🟡' : '🔴'}
                    {' '}{difficultyRec.reason}
                  </p>
                )}
                {(difficultyRec.cautions ?? []).map((c: string, i: number) => (
                  <p key={i} className="text-xs text-amber-600 flex items-start gap-1">
                    <span>⚠️</span>{c}
                  </p>
                ))}
              </div>
            )}
            <button onClick={generateMore} disabled={generating}
              className="bg-amber-500 text-white text-sm px-3 py-1.5 rounded-lg font-medium hover:bg-amber-600 disabled:opacity-50 flex items-center gap-1">
              {generating ? (
                <><div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" /> Generating...</>
              ) : '✨ Generate'}
            </button>
          </div>

          {loadingEx ? <LoadingSpinner text="Loading questions..." /> : exercises.length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-6">No questions yet. Generate some above!</p>
          ) : (
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {exercises.map((ex) => (
                <div key={ex.id} onClick={() => toggle(ex.id)}
                  className={`flex items-start gap-3 p-3 rounded-xl cursor-pointer transition-all border-2 ${
                    selectedIds.has(ex.id) ? 'border-primary-400 bg-primary-50' : 'border-transparent bg-gray-50 hover:bg-gray-100'}`}>
                  <div className="mt-0.5 shrink-0 text-primary-500">
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
          )}
        </div>
      )}

      {/* Step 3: Create */}
      {selectedChapter && selectedIds.size > 0 && (
        <div className="card">
          <h2 className="font-semibold text-gray-700 mb-3">3. Name & Start</h2>
          <input className="input-field mb-3" value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Fractions revision" />
          <div className="bg-blue-50 rounded-xl p-3 text-sm text-blue-700 mb-3 flex items-start gap-2">
            <span className="shrink-0">ℹ️</span>
            <span>Explanations shown <strong>after you submit</strong>. You won't see answers during the attempt.</span>
          </div>
          <button onClick={create} disabled={saving}
            className="btn-primary w-full flex items-center justify-center gap-2">
            <Plus size={18} /> {saving ? 'Starting...' : `Start Practice (${selectedIds.size} question${selectedIds.size !== 1 ? 's' : ''})`}
          </button>
        </div>
      )}
    </Layout>
  )
}
