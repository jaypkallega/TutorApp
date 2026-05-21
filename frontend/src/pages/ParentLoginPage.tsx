import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'
import { useAuthStore } from '../store/authStore'

export default function ParentLoginPage() {
  const [pin, setPin] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const setUser = useAuthStore((s) => s.setUser)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/auth/parent/login', { pin })
      setUser(res.data)
      navigate('/parent/dashboard')
    } catch {
      setError('Incorrect PIN. Please try again.')
      setPin('')
    } finally {
      setLoading(false)
    }
  }

  const appendDigit = (d: string) => {
    if (pin.length < 8) setPin((p) => p + d)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-amber-50 px-4">
      <div className="bg-white rounded-3xl shadow-lg p-8 w-full max-w-sm">
        <div className="text-center mb-6">
          <div className="text-4xl mb-2">🔐</div>
          <h1 className="text-xl font-bold text-gray-800">Parent Login</h1>
          <p className="text-gray-500 text-sm mt-1">Enter your PIN to continue</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* PIN display */}
          <div className="flex justify-center gap-2 py-3">
            {Array.from({ length: Math.max(pin.length, 4) }).map((_, i) => (
              <div
                key={i}
                className={`w-4 h-4 rounded-full transition-all ${
                  i < pin.length ? 'bg-primary-500 scale-110' : 'bg-gray-200'
                }`}
              />
            ))}
          </div>

          {/* Hidden input for real keyboard on desktop */}
          <input
            type="password"
            inputMode="numeric"
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 8))}
            className="input-field text-center tracking-widest text-xl"
            placeholder="····"
            autoFocus
          />

          {/* Number pad for iPad */}
          <div className="grid grid-cols-3 gap-2 mt-2">
            {['1','2','3','4','5','6','7','8','9','','0','⌫'].map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => {
                  if (d === '⌫') setPin((p) => p.slice(0, -1))
                  else if (d) appendDigit(d)
                }}
                disabled={!d}
                className={`h-14 rounded-xl text-xl font-semibold transition-all active:scale-95 ${
                  d === '⌫'
                    ? 'bg-red-50 text-red-500 hover:bg-red-100'
                    : d
                    ? 'bg-gray-100 text-gray-800 hover:bg-gray-200'
                    : 'invisible'
                }`}
              >
                {d}
              </button>
            ))}
          </div>

          {error && (
            <div className="bg-red-50 text-red-600 rounded-xl p-3 text-sm text-center">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn-primary w-full"
            disabled={loading || pin.length < 4}
          >
            {loading ? 'Checking...' : 'Unlock →'}
          </button>
        </form>

        <p className="text-center mt-4">
          <a href="/child/home" className="text-primary-500 text-sm font-medium">
            I'm the child →
          </a>
        </p>
      </div>
    </div>
  )
}
