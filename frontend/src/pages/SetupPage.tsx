import { useState } from 'react'
import api from '../api/client'
import { useAuthStore } from '../store/authStore'

export default function SetupPage() {
  const [form, setForm] = useState({
    parent_display_name: '',
    parent_pin: '',
    child_display_name: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const setUser = useAuthStore((s) => s.setUser)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!/^\d{4,8}$/.test(form.parent_pin)) {
      setError('PIN must be 4–8 digits (numbers only)')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/auth/setup', form)
      setUser(res.data)
      // Full reload so App.tsx re-checks setup status and routes correctly
      window.location.href = '/parent/settings'
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Setup failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-amber-50 px-4">
      <div className="bg-white rounded-3xl shadow-lg p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">🎓</div>
          <h1 className="text-2xl font-bold text-gray-800">Welcome to MathTutor</h1>
          <p className="text-gray-500 mt-1">Let's get set up — this only takes a minute</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">
              Your Name (Parent)
            </label>
            <input
              className="input-field"
              value={form.parent_display_name}
              onChange={(e) => setForm({ ...form, parent_display_name: e.target.value })}
              placeholder="e.g. Dad or Mum"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">
              Your PIN (4–8 digits)
            </label>
            <input
              className="input-field"
              type="password"
              inputMode="numeric"
              maxLength={8}
              value={form.parent_pin}
              onChange={(e) => setForm({ ...form, parent_pin: e.target.value.replace(/\D/g, '') })}
              placeholder="e.g. 1234"
              required
            />
            <p className="text-xs text-gray-400 mt-1">Numbers only. You'll use this to access the parent dashboard.</p>
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">
              Child's Name
            </label>
            <input
              className="input-field"
              value={form.child_display_name}
              onChange={(e) => setForm({ ...form, child_display_name: e.target.value })}
              placeholder="e.g. Saanvi"
              required
            />
          </div>

          {error && (
            <div className="bg-red-50 text-red-600 rounded-xl p-3 text-sm">{error}</div>
          )}

          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? 'Setting up...' : 'Complete Setup →'}
          </button>
        </form>

        <p className="text-center text-xs text-gray-400 mt-6">
          Everything stays on your home network — no data leaves your device.
        </p>
      </div>
    </div>
  )
}
