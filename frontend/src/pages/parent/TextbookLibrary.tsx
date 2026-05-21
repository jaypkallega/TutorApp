import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import Layout from '../../components/Layout'
import LoadingSpinner from '../../components/LoadingSpinner'
import api from '../../api/client'
import { Upload, BookOpen, CheckCircle2, Clock, AlertCircle, ChevronDown, ChevronRight, Trash2 } from 'lucide-react'

interface Textbook {
  id: number
  title: string
  grade: number
  status: string
  page_count: number | null
  upload_type: string
  created_at: string
  analysis_log: string | null
}

interface Chapter {
  id: number
  chapter_number: number
  title: string
  summary: string | null
  approved: boolean
  start_page: number | null
  end_page: number | null
  concepts: { id: number; concept_name: string; explanation: string }[]
}

const STATUS_ICON: Record<string, JSX.Element> = {
  pending:    <Clock size={16} className="text-gray-400" />,
  processing: <div className="w-4 h-4 border-2 border-primary-300 border-t-primary-600 rounded-full animate-spin" />,
  ready:      <CheckCircle2 size={16} className="text-green-500" />,
  error:      <AlertCircle size={16} className="text-red-400" />,
}

export default function TextbookLibrary() {
  const { isParent } = useAuthStore()
  const navigate = useNavigate()
  const [textbooks, setTextbooks] = useState<Textbook[]>([])
  const [chapters, setChapters] = useState<Record<number, Chapter[]>>({})
  const [expandedBook, setExpandedBook] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadForm, setUploadForm] = useState({ title: '', grade: '8', subject: 'Mathematics' })
  const [uploadError, setUploadError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!isParent()) { navigate('/parent/login'); return }
    loadTextbooks()
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [isParent, navigate])

  const loadTextbooks = () => {
    api.get('/textbooks').then((r) => {
      setTextbooks(r.data.items)
      // Poll if any are processing
      const processing = r.data.items.some((t: Textbook) => t.status === 'processing' || t.status === 'pending')
      if (processing && !pollRef.current) {
        pollRef.current = setInterval(() => {
          api.get('/textbooks').then((r2) => {
            setTextbooks(r2.data.items)
            const stillProcessing = r2.data.items.some((t: Textbook) => t.status === 'processing' || t.status === 'pending')
            if (!stillProcessing && pollRef.current) {
              clearInterval(pollRef.current)
              pollRef.current = null
            }
          })
        }, 3000)
      }
    }).finally(() => setLoading(false))
  }

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (!file) { setUploadError('Please select a file'); return }
    if (!uploadForm.title.trim()) { setUploadError('Please enter a title'); return }

    setUploading(true)
    setUploadError('')
    const fd = new FormData()
    fd.append('title', uploadForm.title)
    fd.append('grade', uploadForm.grade)
    fd.append('subject', uploadForm.subject)
    fd.append('file', file)

    try {
      await api.post('/textbooks', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setUploadForm({ title: '', grade: '8', subject: 'Mathematics' })
      if (fileRef.current) fileRef.current.value = ''
      loadTextbooks()
    } catch (e: any) {
      setUploadError(e.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const loadChapters = async (textbookId: number) => {
    if (chapters[textbookId]) return
    const r = await api.get(`/chapters?textbook_id=${textbookId}`)
    setChapters((prev) => ({ ...prev, [textbookId]: r.data }))
  }

  const toggleBook = async (id: number) => {
    if (expandedBook === id) { setExpandedBook(null); return }
    setExpandedBook(id)
    await loadChapters(id)
  }

  const toggleApprove = async (chapter: Chapter, tbId: number) => {
    await api.patch(`/chapters/${chapter.id}`, { approved: !chapter.approved })
    setChapters((prev) => ({
      ...prev,
      [tbId]: prev[tbId].map((c) => c.id === chapter.id ? { ...c, approved: !c.approved } : c),
    }))
  }

  const deleteTextbook = async (id: number) => {
    if (!confirm('Delete this textbook and all its chapters? This cannot be undone.')) return
    await api.delete(`/textbooks/${id}`)
    setTextbooks((prev) => prev.filter((t) => t.id !== id))
  }

  if (loading) return <Layout title="Textbook Library"><LoadingSpinner /></Layout>

  return (
    <Layout title="Textbook Library">
      {/* Upload form */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Upload size={20} /> Upload Textbook
        </h2>
        <form onSubmit={handleUpload} className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
              <input
                className="input-field"
                value={uploadForm.title}
                onChange={(e) => setUploadForm({ ...uploadForm, title: e.target.value })}
                placeholder="e.g. NCERT Mathematics Grade 8"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Grade</label>
              <select
                className="input-field"
                value={uploadForm.grade}
                onChange={(e) => setUploadForm({ ...uploadForm, grade: e.target.value })}
              >
                {[6, 7, 8, 9, 10, 11, 12].map((g) => <option key={g} value={g}>Grade {g}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Subject</label>
              <select
                className="input-field"
                value={uploadForm.subject}
                onChange={(e) => setUploadForm({ ...uploadForm, subject: e.target.value })}
              >
                {['Mathematics','Science','Physics','Chemistry','Biology','Social Science','English','History','Geography'].map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">PDF File</label>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-primary-50 file:text-primary-700 file:font-medium hover:file:bg-primary-100"
            />
            <p className="text-xs text-gray-400 mt-1">PDF or scanned images. Max 100 MB.</p>
          </div>
          {uploadError && <div className="text-red-500 text-sm bg-red-50 p-3 rounded-xl">{uploadError}</div>}
          <button type="submit" className="btn-primary" disabled={uploading}>
            {uploading ? 'Uploading...' : 'Upload & Analyze'}
          </button>
        </form>
      </div>

      {/* Textbook list */}
      <div className="space-y-3">
        {textbooks.length === 0 && (
          <div className="card text-center text-gray-400 py-12">
            <BookOpen size={40} className="mx-auto mb-3 text-gray-300" />
            <p>No textbooks yet. Upload your first one above.</p>
          </div>
        )}

        {textbooks.map((tb) => (
          <div key={tb.id} className="card p-0 overflow-hidden">
            {/* Header row */}
            <div
              className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50"
              onClick={() => tb.status === 'ready' && toggleBook(tb.id)}
            >
              <div className="flex items-center gap-3">
                {STATUS_ICON[tb.status] || STATUS_ICON.pending}
                <div>
                  <div className="font-semibold text-gray-800">{tb.title}</div>
                  <div className="text-sm text-gray-500">
                    Grade {tb.grade} · {tb.page_count ? `${tb.page_count} pages` : 'Processing...'}
                    {tb.analysis_log && <span className="ml-2 text-xs text-gray-400">{tb.analysis_log}</span>}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={(e) => { e.stopPropagation(); deleteTextbook(tb.id) }}
                  className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all">
                  <Trash2 size={16} />
                </button>
                {tb.status === 'ready' && (
                  expandedBook === tb.id ? <ChevronDown size={18} /> : <ChevronRight size={18} />
                )}
              </div>
            </div>

            {/* Chapters */}
            {expandedBook === tb.id && chapters[tb.id] && (
              <div className="border-t border-gray-100 bg-gray-50 p-4 space-y-2">
                <p className="text-xs text-gray-500 font-semibold uppercase tracking-wide mb-3">
                  {chapters[tb.id].length} Chapters · Click to approve for assignments
                </p>
                {chapters[tb.id].map((ch) => (
                  <div key={ch.id} className="bg-white rounded-xl p-3 flex items-start gap-3">
                    <button
                      onClick={() => toggleApprove(ch, tb.id)}
                      className={`mt-0.5 w-5 h-5 rounded-full border-2 flex-shrink-0 transition-all ${
                        ch.approved ? 'bg-green-500 border-green-500' : 'border-gray-300 hover:border-primary-400'
                      }`}
                    >
                      {ch.approved && <CheckCircle2 size={12} className="text-white m-auto" />}
                    </button>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-800 text-sm">
                        Ch. {ch.chapter_number}: {ch.title}
                      </div>
                      {ch.summary && <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{ch.summary}</p>}
                      {ch.concepts.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {ch.concepts.slice(0, 3).map((c) => (
                            <span key={c.id} className="bg-primary-50 text-primary-700 text-xs px-2 py-0.5 rounded-full">
                              {c.concept_name}
                            </span>
                          ))}
                          {ch.concepts.length > 3 && (
                            <span className="text-xs text-gray-400">+{ch.concepts.length - 3} more</span>
                          )}
                        </div>
                      )}
                    </div>
                    {ch.start_page && (
                      <span className="text-xs text-gray-400 shrink-0">pp. {ch.start_page}–{ch.end_page}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </Layout>
  )
}
