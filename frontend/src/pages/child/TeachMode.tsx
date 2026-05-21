import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout'
import LoadingSpinner from '../../components/LoadingSpinner'
import api from '../../api/client'
import { Send, BookOpen, Trophy, Sparkles, ArrowRight } from 'lucide-react'

interface Message { role: 'user' | 'assistant'; content: string; phase: string; timestamp: string }
interface Concept { id: number; concept_name: string; explanation: string }
interface Chapter { id: number; title: string; chapter_number: number; concepts: Concept[] }

const PHASE_LABELS: Record<string, { label: string; color: string; desc: string }> = {
  hook:        { label: 'Warm Up',    color: 'bg-amber-100 text-amber-700',   desc: 'Getting curious...' },
  explore:     { label: 'Explore',    color: 'bg-blue-100 text-blue-700',     desc: 'Discovering patterns' },
  generalise:  { label: 'Understand', color: 'bg-purple-100 text-purple-700', desc: 'Making sense of it' },
  example:     { label: 'Example',    color: 'bg-teal-100 text-teal-700',     desc: 'Working it through' },
  practice:    { label: 'Practice',   color: 'bg-green-100 text-green-700',   desc: 'Try it yourself' },
  complete:    { label: 'Done! 🎉',   color: 'bg-green-200 text-green-800',   desc: 'Concept learned' },
}

const PHASE_ORDER = ['hook', 'explore', 'generalise', 'example', 'practice', 'complete']

export default function TeachMode() {
  const { chapterId } = useParams<{ chapterId: string }>()
  const navigate = useNavigate()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const [chapter, setChapter] = useState<Chapter | null>(null)
  const [selectedConcept, setSelectedConcept] = useState<Concept | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [phase, setPhase] = useState('hook')
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [aiTyping, setAiTyping] = useState(false)
  const [sessionComplete, setSessionComplete] = useState(false)
  const [progress, setProgress] = useState<Record<number, any>>({})
  const [starting, setStarting] = useState(false)

  useEffect(() => {
    api.get(`/chapters/${chapterId}`)
      .then((r) => setChapter(r.data))
      .catch(() => navigate('/child/home'))
      .finally(() => setLoading(false))
    // Load progress for all concepts in this chapter
    api.get('/teach/progress').then((r) => {
      const map: Record<number, any> = {}
      r.data.forEach((p: any) => { map[p.concept_id] = p })
      setProgress(map)
    }).catch(() => {})
  }, [chapterId, navigate])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const startConcept = async (concept: Concept) => {
    setSelectedConcept(concept)
    setStarting(true)
    setMessages([])
    setSessionComplete(false)
    try {
      const r = await api.post('/teach/session/start', { concept_id: concept.id })
      setSessionId(r.data.session_id)
      setMessages(r.data.messages || [])
      setPhase(r.data.phase || 'hook')
      if (r.data.is_resume) setPhase(r.data.phase)
    } catch {
      setMessages([{ role: 'assistant', content: 'Sorry, the AI tutor is not available right now. Check your LLM settings.', phase: 'hook', timestamp: new Date().toISOString() }])
    } finally {
      setStarting(false)
      setTimeout(() => inputRef.current?.focus(), 200)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || !sessionId || aiTyping) return
    const userMsg: Message = { role: 'user', content: input.trim(), phase, timestamp: new Date().toISOString() }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setAiTyping(true)
    try {
      const r = await api.post('/teach/session/message', { session_id: sessionId, message: userMsg.content })
      setMessages(r.data.messages || [])
      setPhase(r.data.phase || phase)
      if (r.data.session_complete) setSessionComplete(true)
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: 'Sorry, something went wrong. Please try again.', phase, timestamp: new Date().toISOString() }])
    } finally {
      setAiTyping(false)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }

  const phaseIdx = PHASE_ORDER.indexOf(phase)

  if (loading) return <Layout title="Learn"><LoadingSpinner /></Layout>
  if (!chapter) return <Layout title="Learn"><div className="card text-center text-gray-400">Chapter not found</div></Layout>

  // Concept selector screen
  if (!selectedConcept) {
    return (
      <Layout title={`Learn: ${chapter.title}`}>
        <div className="mb-6">
          <h1 className="text-xl font-bold text-gray-800">Ch. {chapter.chapter_number}: {chapter.title}</h1>
          <p className="text-gray-500 text-sm mt-1">Choose a concept to learn with your AI tutor.</p>
        </div>

        {chapter.concepts.length === 0 ? (
          <div className="card text-center text-gray-400 py-10">No concepts found for this chapter yet.</div>
        ) : (
          <div className="space-y-3">
            {chapter.concepts.map((concept) => {
              const prog = progress[concept.id]
              const mastery = prog?.mastery_level || 'not_started'
              const MASTERY_CONFIG: Record<string, { icon: string; color: string; label: string }> = {
                not_started: { icon: '○', color: 'text-gray-400', label: 'Not started' },
                introduced:  { icon: '◑', color: 'text-blue-500', label: 'Introduced' },
                practised:   { icon: '◕', color: 'text-amber-500', label: 'Practised' },
                mastered:    { icon: '●', color: 'text-green-500', label: 'Mastered' },
              }
              const mc = MASTERY_CONFIG[mastery] || MASTERY_CONFIG.not_started
              return (
                <button key={concept.id} onClick={() => startConcept(concept)}
                  className="w-full card hover:shadow-md transition-all flex items-center gap-4 text-left">
                  <div className={`text-2xl font-bold shrink-0 ${mc.color}`}>{mc.icon}</div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-gray-800">{concept.concept_name}</div>
                    <div className="text-sm text-gray-500 mt-0.5 line-clamp-1">{concept.explanation?.slice(0, 80)}...</div>
                    <div className={`text-xs mt-1 font-medium ${mc.color}`}>{mc.label}</div>
                  </div>
                  <Sparkles size={18} className="text-primary-400 shrink-0" />
                </button>
              )
            })}
          </div>
        )}
      </Layout>
    )
  }

  // Teaching session screen
  return (
    <Layout title={selectedConcept.concept_name}>
      <div className="flex flex-col h-[calc(100vh-120px)] max-h-[750px]">
        {/* Header */}
        <div className="flex items-center justify-between mb-3 shrink-0">
          <button onClick={() => setSelectedConcept(null)} className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1">
            ← All concepts
          </button>
          {/* Phase progress bar */}
          <div className="flex items-center gap-1">
            {PHASE_ORDER.slice(0, -1).map((p, i) => (
              <div key={p} className={`h-2 rounded-full transition-all ${i <= phaseIdx ? 'bg-primary-500 w-8' : 'bg-gray-200 w-4'}`} />
            ))}
          </div>
          {PHASE_LABELS[phase] && (
            <span className={`text-xs font-semibold px-2 py-1 rounded-full ${PHASE_LABELS[phase].color}`}>
              {PHASE_LABELS[phase].label}
            </span>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-3 pr-1 pb-2">
          {starting && (
            <div className="flex items-center gap-2 py-4">
              <div className="w-5 h-5 border-2 border-primary-200 border-t-primary-500 rounded-full animate-spin" />
              <p className="text-gray-500 text-sm">Starting your session...</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-primary-50 flex items-center justify-center shrink-0 mr-2 mt-1">
                  <Sparkles size={14} className="text-primary-500" />
                </div>
              )}
              <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-primary-500 text-white rounded-br-md'
                  : 'bg-white border border-gray-100 text-gray-800 rounded-bl-md shadow-sm'
              }`}>
                {msg.content}
              </div>
            </div>
          ))}

          {aiTyping && (
            <div className="flex justify-start">
              <div className="w-8 h-8 rounded-full bg-primary-50 flex items-center justify-center shrink-0 mr-2">
                <Sparkles size={14} className="text-primary-500" />
              </div>
              <div className="bg-white border border-gray-100 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Completion banner */}
        {sessionComplete && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-3 text-center shrink-0">
            <Trophy size={24} className="mx-auto mb-1 text-green-500" />
            <p className="font-semibold text-green-800">Concept learned! 🎉</p>
            <p className="text-sm text-green-600 mt-1">This concept is now unlocked for practice exercises.</p>
            <div className="flex gap-2 mt-3 justify-center">
              <button onClick={() => setSelectedConcept(null)} className="btn-secondary text-sm px-4 py-2">
                Learn another →
              </button>
              <button onClick={() => navigate(`/child/home`)} className="btn-primary text-sm px-4 py-2 flex items-center gap-1">
                <BookOpen size={14} /> Go practise
              </button>
            </div>
          </div>
        )}

        {/* Input */}
        {!sessionComplete && (
          <div className="flex gap-2 pt-2 shrink-0">
            <input
              ref={inputRef}
              className="input-field flex-1 text-sm"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
              placeholder="Type your answer or question..."
              disabled={aiTyping || starting}
            />
            <button onClick={sendMessage} disabled={!input.trim() || aiTyping || starting}
              className="p-3 bg-primary-500 text-white rounded-xl hover:bg-primary-600 disabled:opacity-40 transition-all">
              <Send size={18} />
            </button>
          </div>
        )}
      </div>
    </Layout>
  )
}
