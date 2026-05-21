import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout'
import LoadingSpinner from '../../components/LoadingSpinner'
import api from '../../api/client'
import { ChevronLeft, ChevronRight, Sparkles, Send } from 'lucide-react'

interface Concept {
  id: number
  concept_name: string
  explanation: string
  textbook_method: string | null
  alternate_method: string | null
  difficulty_hint: string | null
  ordering: number
}

interface Chapter {
  id: number
  title: string
  chapter_number: number
  concepts: Concept[]
}

export default function LearnMode() {
  const { chapterId } = useParams<{ chapterId: string }>()
  const navigate = useNavigate()
  const [chapter, setChapter] = useState<Chapter | null>(null)
  const [currentIdx, setCurrentIdx] = useState(0)
  const [loading, setLoading] = useState(true)
  const [aiExplanation, setAiExplanation] = useState<string | null>(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [question, setQuestion] = useState('')

  useEffect(() => {
    api.get(`/chapters/${chapterId}`)
      .then((r) => setChapter(r.data))
      .catch(() => navigate('/child/home'))
      .finally(() => setLoading(false))
  }, [chapterId, navigate])

  const concept = chapter?.concepts[currentIdx]

  const askAI = async (q?: string) => {
    if (!concept) return
    setAiLoading(true)
    setAiExplanation(null)
    try {
      const r = await api.post(`/chapters/${chapterId}/explain`, null, {
        params: { concept_id: concept.id, question: q || undefined },
      })
      setAiExplanation(r.data.explanation)
    } catch {
      setAiExplanation("Sorry, I couldn't connect to the AI tutor. Check that your LLM API key is configured.")
    } finally {
      setAiLoading(false)
      setQuestion('')
    }
  }

  const prev = () => { setCurrentIdx((i) => Math.max(0, i - 1)); setAiExplanation(null) }
  const next = () => { setCurrentIdx((i) => Math.min((chapter?.concepts.length ?? 1) - 1, i + 1)); setAiExplanation(null) }

  if (loading || !chapter) return <Layout title="Learn"><LoadingSpinner /></Layout>
  if (!chapter.concepts.length) {
    return (
      <Layout title={chapter.title}>
        <div className="card text-center py-12 text-gray-400">
          No concepts found for this chapter yet.
        </div>
      </Layout>
    )
  }

  return (
    <Layout title={`Ch. ${chapter.chapter_number}: ${chapter.title}`}>
      {/* Progress bar */}
      <div className="mb-4">
        <div className="flex justify-between text-sm text-gray-500 mb-1">
          <span>Concept {currentIdx + 1} of {chapter.concepts.length}</span>
          <span>{Math.round(((currentIdx + 1) / chapter.concepts.length) * 100)}%</span>
        </div>
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-primary-500 rounded-full transition-all"
            style={{ width: `${((currentIdx + 1) / chapter.concepts.length) * 100}%` }}
          />
        </div>
      </div>

      {concept && (
        <div className="space-y-4">
          {/* Concept card */}
          <div className="card">
            <h2 className="text-xl font-bold text-gray-800 mb-3">{concept.concept_name}</h2>
            <p className="text-gray-700 leading-relaxed whitespace-pre-line">{concept.explanation}</p>

            {concept.textbook_method && (
              <div className="mt-4 p-4 bg-blue-50 rounded-xl">
                <p className="text-sm font-semibold text-blue-700 mb-1">📖 Textbook Method</p>
                <p className="text-sm text-blue-800 whitespace-pre-line">{concept.textbook_method}</p>
              </div>
            )}

            {concept.alternate_method && (
              <div className="mt-3 p-4 bg-purple-50 rounded-xl">
                <p className="text-sm font-semibold text-purple-700 mb-1">💡 Another Way to Think About It</p>
                <p className="text-sm text-purple-800 whitespace-pre-line">{concept.alternate_method}</p>
              </div>
            )}

            {concept.difficulty_hint && (
              <div className="mt-3 p-4 bg-amber-50 rounded-xl">
                <p className="text-sm font-semibold text-amber-700 mb-1">⚠️ Watch Out</p>
                <p className="text-sm text-amber-800">{concept.difficulty_hint}</p>
              </div>
            )}
          </div>

          {/* AI Tutor */}
          <div className="card">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles size={18} className="text-primary-500" />
              <h3 className="font-semibold text-gray-700">Ask the AI Tutor</h3>
            </div>

            {!aiExplanation && !aiLoading && (
              <button
                onClick={() => askAI()}
                className="btn-primary w-full mb-3 flex items-center justify-center gap-2"
              >
                <Sparkles size={16} /> Explain this to me with an example
              </button>
            )}

            {aiLoading && (
              <div className="flex items-center gap-3 py-4">
                <div className="w-6 h-6 border-3 border-primary-200 border-t-primary-500 rounded-full animate-spin" />
                <p className="text-gray-500 text-sm">Thinking...</p>
              </div>
            )}

            {aiExplanation && (
              <div className="bg-primary-50 rounded-xl p-4 mb-3">
                <p className="text-gray-800 leading-relaxed whitespace-pre-line text-sm">{aiExplanation}</p>
              </div>
            )}

            {/* Ask a specific question */}
            <div className="flex gap-2 mt-2">
              <input
                className="input-field flex-1 text-sm"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && question.trim() && askAI(question)}
                placeholder="Ask a question about this concept..."
              />
              <button
                onClick={() => question.trim() && askAI(question)}
                disabled={!question.trim() || aiLoading}
                className="p-3 bg-primary-500 text-white rounded-xl hover:bg-primary-600 disabled:opacity-40 transition-all"
              >
                <Send size={18} />
              </button>
            </div>
          </div>

          {/* Navigation */}
          <div className="flex gap-3">
            <button onClick={prev} disabled={currentIdx === 0} className="btn-secondary flex-1 flex items-center justify-center gap-2">
              <ChevronLeft size={18} /> Previous
            </button>
            {currentIdx < chapter.concepts.length - 1 ? (
              <button onClick={next} className="btn-primary flex-1 flex items-center justify-center gap-2">
                Next <ChevronRight size={18} />
              </button>
            ) : (
              <button onClick={() => navigate('/child/home')} className="btn-primary flex-1">
                All done! 🎉
              </button>
            )}
          </div>
        </div>
      )}
    </Layout>
  )
}
