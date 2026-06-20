import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import Layout from '../../components/Layout'
import LoadingSpinner from '../../components/LoadingSpinner'
import api from '../../api/client'
import { Upload, BookOpen, CheckCircle2, Clock, AlertCircle, ChevronDown, ChevronRight, Trash2, Pencil, Check, X } from 'lucide-react'

interface Textbook {
  id: number; title: string; grade: number; status: string
  page_count: number | null; upload_type: string
  created_at: string; analysis_log: string | null
}
interface Chapter {
  id: number; chapter_number: number; title: string
  summary: string | null; approved: boolean
  start_page: number | null; end_page: number | null
  concepts: { id: number; concept_name: string; explanation: string }[]
}
interface FileRow {
  id: string; file: File; title: string; grade: string; subject: string
  status: 'pending' | 'uploading' | 'done' | 'error'; error: string
}

const STATUS_ICON: Record<string, JSX.Element> = {
  pending:    <Clock size={16} className="text-gray-400" />,
  processing: <div className="w-4 h-4 border-2 border-primary-300 border-t-primary-600 rounded-full animate-spin" />,
  ready:      <CheckCircle2 size={16} className="text-green-500" />,
  error:      <AlertCircle size={16} className="text-red-400" />,
}
const SUBJECTS = ['Mathematics','Science','Physics','Chemistry','Biology','Social Science','English','History','Geography']
const GRADES = [6, 7, 8, 9, 10, 11, 12]

function guessTitle(f: string) { return f.replace(/\.[^.]+$/, '').replace(/[-_]/g, ' ').trim() }

export default function TextbookLibrary() {
  const { isParent } = useAuthStore()
  const navigate = useNavigate()
  const [textbooks, setTextbooks] = useState<Textbook[]>([])
  const [chapters, setChapters] = useState<Record<number, Chapter[]>>({})
  const [expandedBook, setExpandedBook] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploadingAll, setUploadingAll] = useState(false)
  const [fileRows, setFileRows] = useState<FileRow[]>([])
  const fileRef = useRef<HTMLInputElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const editInputRef = useRef<HTMLInputElement>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editingTitle, setEditingTitle] = useState('')

  useEffect(() => {
    if (!isParent()) { navigate('/parent/login'); return }
    loadTextbooks()
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [isParent, navigate])

  const loadTextbooks = () => {
    api.get('/textbooks').then((r) => {
      setTextbooks(r.data.items)
      const processing = r.data.items.some((t: Textbook) => t.status === 'processing' || t.status === 'pending')
      if (processing && !pollRef.current) {
        pollRef.current = setInterval(() => {
          api.get('/textbooks').then((r2) => {
            setTextbooks(r2.data.items)
            if (!r2.data.items.some((t: Textbook) => t.status === 'processing' || t.status === 'pending')) {
              clearInterval(pollRef.current!); pollRef.current = null
            }
          })
        }, 3000)
      }
    }).finally(() => setLoading(false))
  }

  const onFilesSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    setFileRows((prev) => [
      ...prev,
      ...files.map((f) => ({
        id: `${f.name}-${f.size}-${Math.random()}`,
        file: f, title: guessTitle(f.name),
        grade: '8', subject: 'Mathematics',
        status: 'pending' as const, error: '',
      })),
    ])
    if (fileRef.current) fileRef.current.value = ''
  }

  const removeRow = (id: string) => setFileRows((p) => p.filter((r) => r.id !== id))
  const updateRow = (id: string, patch: Partial<FileRow>) =>
    setFileRows((p) => p.map((r) => r.id === id ? { ...r, ...patch } : r))

  const uploadAll = async () => {
    const pending = fileRows.filter((r) => r.status === 'pending')
    if (!pending.length) return
    for (const row of pending) {
      if (!row.title.trim()) { updateRow(row.id, { status: 'error', error: 'Title is required' }); return }
    }
    setUploadingAll(true)
    for (const row of pending) {
      updateRow(row.id, { status: 'uploading', error: '' })
      const fd = new FormData()
      fd.append('title', row.title.trim()); fd.append('grade', row.grade)
      fd.append('subject', row.subject); fd.append('file', row.file)
      try {
        await api.post('/textbooks', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
        updateRow(row.id, { status: 'done' })
      } catch (e: any) {
        updateRow(row.id, { status: 'error', error: e.response?.data?.detail || 'Upload failed' })
      }
    }
    setUploadingAll(false)
    setFileRows((p) => p.filter((r) => r.status !== 'done'))
    loadTextbooks()
  }

  const loadChapters = async (textbookId: number) => {
    if (chapters[textbookId]) return
    const r = await api.get(`/chapters?textbook_id=${textbookId}`)
    setChapters((prev) => ({ ...prev, [textbookId]: r.data }))
  }
  const toggleBook = async (id: number) => {
    if (expandedBook === id) { setExpandedBook(null); return }
    setExpandedBook(id); await loadChapters(id)
  }
  const toggleApprove = async (chapter: Chapter, tbId: number) => {
    await api.patch(`/chapters/${chapter.id}`, { approved: !chapter.approved })
    setChapters((prev) => ({
      ...prev, [tbId]: prev[tbId].map((c) => c.id === chapter.id ? { ...c, approved: !c.approved } : c),
    }))
  }
  const deleteTextbook = async (id: number) => {
    if (!confirm('Delete this textbook and all its chapters?')) return
    await api.delete(`/textbooks/${id}`)
    setTextbooks((p) => p.filter((t) => t.id !== id))
  }
  const startEdit = (tb: Textbook, e: React.MouseEvent) => {
    e.stopPropagation(); setEditingId(tb.id); setEditingTitle(tb.title)
    setTimeout(() => editInputRef.current?.focus(), 0)
  }
  const saveTitle = async (id: number) => {
    const trimmed = editingTitle.trim()
    if (!trimmed) { setEditingId(null); return }
    try {
      await api.patch(`/textbooks/${id}`, { title: trimmed })
      setTextbooks((p) => p.map((t) => t.id === id ? { ...t, title: trimmed } : t))
    } catch {}
    setEditingId(null)
  }

  if (loading) return <Layout title="Textbook Library"><LoadingSpinner /></Layout>

  const pendingRows = fileRows.filter((r) => r.status === 'pending')

  return (
    <Layout title="Textbook Library">
      {/* Upload section */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Upload size={20} /> Upload Textbooks
        </h2>

        {/* Drop zone */}
        <div
          className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center cursor-pointer hover:border-primary-300 hover:bg-primary-50/30 transition-all mb-4"
          onClick={() => fileRef.current?.click()}
        >
          <Upload size={28} className="mx-auto mb-2 text-gray-300" />
          <p className="text-gray-500 font-medium text-sm">Click to select PDF or image files</p>
          <p className="text-xs text-gray-400 mt-1">Select multiple files at once · Max 100 MB each</p>
          <input ref={fileRef} type="file" accept=".pdf,.png,.jpg,.jpeg" multiple className="hidden" onChange={onFilesSelected} />
        </div>

        {/* File rows */}
        {fileRows.length > 0 && (
          <div className="space-y-3 mb-4">
            {fileRows.map((row) => (
              <div key={row.id} className={`rounded-xl border-2 p-3 transition-all ${
                row.status === 'done'      ? 'border-green-200 bg-green-50' :
                row.status === 'error'     ? 'border-red-200 bg-red-50' :
                row.status === 'uploading' ? 'border-primary-200 bg-primary-50/40' :
                                             'border-gray-100 bg-gray-50'
              }`}>
                {/* File name */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    {row.status === 'uploading' && <div className="w-4 h-4 border-2 border-primary-400 border-t-transparent rounded-full animate-spin shrink-0" />}
                    {row.status === 'done'      && <CheckCircle2 size={16} className="text-green-500 shrink-0" />}
                    {row.status === 'error'     && <AlertCircle  size={16} className="text-red-400   shrink-0" />}
                    <span className="text-sm font-medium text-gray-700 truncate">{row.file.name}</span>
                    <span className="text-xs text-gray-400 shrink-0">{(row.file.size/1024/1024).toFixed(1)} MB</span>
                  </div>
                  {row.status !== 'uploading' && (
                    <button onClick={() => removeRow(row.id)} className="text-gray-400 hover:text-red-500 p-1 rounded shrink-0">
                      <X size={14} />
                    </button>
                  )}
                </div>
                {row.error && <p className="text-xs text-red-500 mb-2">{row.error}</p>}
                {row.status === 'done' && <p className="text-xs text-green-600 font-medium">? Uploaded — analysing in background</p>}
                {(row.status === 'pending' || row.status === 'error') && (
                  <div className="grid grid-cols-3 gap-2">
                    <div className="col-span-3 sm:col-span-1">
                      <label className="block text-xs text-gray-500 mb-1">Title *</label>
                      <input className="input-field text-sm py-1.5" value={row.title} placeholder="Textbook title"
                        onChange={(e) => updateRow(row.id, { title: e.target.value })} />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Grade</label>
                      <select className="input-field text-sm py-1.5" value={row.grade}
                        onChange={(e) => updateRow(row.id, { grade: e.target.value })}>
                        {GRADES.map((g) => <option key={g} value={g}>Grade {g}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Subject</label>
                      <select className="input-field text-sm py-1.5" value={row.subject}
                        onChange={(e) => updateRow(row.id, { subject: e.target.value })}>
                        {SUBJECTS.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {pendingRows.length > 0 && (
          <div className="flex items-center gap-3">
            <button onClick={uploadAll} disabled={uploadingAll} className="btn-primary flex items-center gap-2 disabled:opacity-50">
              <Upload size={16} />
              {uploadingAll ? 'Uploading…' : `Upload ${pendingRows.length} file${pendingRows.length > 1 ? 's' : ''} & Analyze`}
            </button>
            <button onClick={() => setFileRows([])} disabled={uploadingAll} className="text-sm text-gray-400 hover:text-gray-600">
              Clear all
            </button>
          </div>
        )}
        {fileRows.length === 0 && <p className="text-xs text-gray-400">PDF or scanned images. Multiple files supported.</p>}
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
            <div className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50"
              onClick={() => tb.status === 'ready' && toggleBook(tb.id)}>
              <div className="flex items-center gap-3">
                {STATUS_ICON[tb.status] || STATUS_ICON.pending}
                <div>
                  {editingId === tb.id ? (
                    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                      <input ref={editInputRef} id={`title-edit-${tb.id}`}
                        className="text-sm font-semibold text-gray-800 border-b-2 border-primary-400 bg-transparent outline-none px-0.5 w-48"
                        value={editingTitle} onChange={(e) => setEditingTitle(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') saveTitle(tb.id); if (e.key === 'Escape') setEditingId(null) }}
                        onBlur={() => saveTitle(tb.id)} />
                      <button onClick={() => saveTitle(tb.id)} className="text-green-500 p-0.5"><Check size={14} /></button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1 group">
                      <span className="font-semibold text-gray-800">{tb.title}</span>
                      <button onClick={(e) => startEdit(tb, e)} title="Edit title"
                        className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-primary-500 transition-opacity p-0.5 rounded">
                        <Pencil size={13} />
                      </button>
                    </div>
                  )}
                  <div className="text-sm text-gray-500">
                    Grade {tb.grade} · {tb.page_count ? `${tb.page_count} pages` : 'Processing…'}
                    {tb.analysis_log && <span className="ml-2 text-xs text-gray-400">{tb.analysis_log}</span>}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={(e) => { e.stopPropagation(); deleteTextbook(tb.id) }}
                  className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all">
                  <Trash2 size={16} />
                </button>
                {tb.status === 'ready' && (expandedBook === tb.id ? <ChevronDown size={18} /> : <ChevronRight size={18} />)}
              </div>
            </div>

            {expandedBook === tb.id && chapters[tb.id] && (
              <div className="border-t border-gray-100 bg-gray-50 p-4 space-y-2">
                <p className="text-xs text-gray-500 font-semibold uppercase tracking-wide mb-3">
                  {chapters[tb.id].length} Chapters · Click to approve for assignments
                </p>
                {chapters[tb.id].map((ch) => (
                  <div key={ch.id} className="bg-white rounded-xl p-3 flex items-start gap-3">
                    <button onClick={() => toggleApprove(ch, tb.id)}
                      className={`mt-0.5 w-5 h-5 rounded-full border-2 flex-shrink-0 transition-all ${
                        ch.approved ? 'bg-green-500 border-green-500' : 'border-gray-300 hover:border-primary-400'}`}>
                      {ch.approved && <CheckCircle2 size={12} className="text-white m-auto" />}
                    </button>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-800 text-sm">Ch. {ch.chapter_number}: {ch.title}</div>
                      {ch.summary && <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{ch.summary}</p>}
                      {ch.concepts.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {ch.concepts.slice(0, 3).map((c) => (
                            <span key={c.id} className="bg-primary-50 text-primary-700 text-xs px-2 py-0.5 rounded-full">{c.concept_name}</span>
                          ))}
                          {ch.concepts.length > 3 && <span className="text-xs text-gray-400">+{ch.concepts.length - 3} more</span>}
                        </div>
                      )}
                    </div>
                    {ch.start_page && <span className="text-xs text-gray-400 shrink-0">pp. {ch.start_page}–{ch.end_page}</span>}
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
