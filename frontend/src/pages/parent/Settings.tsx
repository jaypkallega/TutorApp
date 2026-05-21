import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import Layout from '../../components/Layout'
import LoadingSpinner from '../../components/LoadingSpinner'
import api from '../../api/client'
import { Save, Wifi, TestTube2, CheckCircle2, XCircle, Eye, EyeOff } from 'lucide-react'

interface Settings {
  llm_provider: string
  llm_api_key: string
  llm_model_name: string
  llm_base_url: string
  ocr_mode: string
  lan_only_mode: string
}

interface NetworkInfo {
  hostname: string
  local_ip: string
  port: number
  access_url: string
  ipad_instructions: string
}

const PROVIDER_MODELS: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  anthropic: ['claude-opus-4-5', 'claude-sonnet-4-5', 'claude-haiku-4-5-20251001'],
  gemini: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro'],
  custom: [],
}

export default function SettingsPage() {
  const { isParent } = useAuthStore()
  const navigate = useNavigate()
  const [settings, setSettings] = useState<Settings | null>(null)
  const [networkInfo, setNetworkInfo] = useState<NetworkInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; latency_ms?: number } | null>(null)
  const [showKey, setShowKey] = useState(false)
  const [saved, setSaved] = useState(false)
  const [apiKeyEditing, setApiKeyEditing] = useState(false)
  const [newApiKey, setNewApiKey] = useState('')

  useEffect(() => {
    if (!isParent()) { navigate('/parent/login'); return }
    Promise.all([
      api.get('/settings'),
      api.get('/settings/network-info'),
    ]).then(([sRes, nRes]) => {
      setSettings(sRes.data)
      setNetworkInfo(nRes.data)
    }).finally(() => setLoading(false))
  }, [isParent, navigate])

  const handleSave = async () => {
    if (!settings) return
    setSaving(true)
    try {
      const payload: Partial<Settings> = { ...settings }
      if (apiKeyEditing && newApiKey) {
        payload.llm_api_key = newApiKey
      } else {
        delete payload.llm_api_key // Don't overwrite with masked value
      }
      await api.put('/settings', payload)
      setSaved(true)
      setApiKeyEditing(false)
      setNewApiKey('')
      setTimeout(() => setSaved(false), 2500)
      // Refresh to get masked key
      const r = await api.get('/settings')
      setSettings(r.data)
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const r = await api.post('/settings/llm/test')
      setTestResult(r.data)
    } catch (e: any) {
      setTestResult({ success: false, message: e.response?.data?.detail || 'Test failed' })
    } finally {
      setTesting(false)
    }
  }

  if (loading || !settings) return <Layout title="Settings"><LoadingSpinner /></Layout>

  const suggestedModels = PROVIDER_MODELS[settings.llm_provider] ?? []

  return (
    <Layout title="Settings">
      <div className="max-w-2xl space-y-6">

        {/* LLM Config */}
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">🤖 AI Model Settings</h2>
          <div className="space-y-4">

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Provider</label>
              <select
                className="input-field"
                value={settings.llm_provider}
                onChange={(e) => setSettings({ ...settings, llm_provider: e.target.value, llm_model_name: PROVIDER_MODELS[e.target.value]?.[0] ?? '' })}
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic (Claude)</option>
                <option value="gemini">Google Gemini</option>
                <option value="custom">Custom (OpenAI-compatible)</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model Name</label>
              {suggestedModels.length > 0 ? (
                <select
                  className="input-field"
                  value={settings.llm_model_name}
                  onChange={(e) => setSettings({ ...settings, llm_model_name: e.target.value })}
                >
                  {suggestedModels.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              ) : (
                <input
                  className="input-field"
                  value={settings.llm_model_name}
                  onChange={(e) => setSettings({ ...settings, llm_model_name: e.target.value })}
                  placeholder="e.g. llama3-70b"
                />
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
              {!apiKeyEditing ? (
                <div className="flex gap-2">
                  <div className="input-field flex-1 text-gray-500 font-mono text-sm bg-gray-50">
                    {settings.llm_api_key || 'Not set'}
                  </div>
                  <button
                    onClick={() => setApiKeyEditing(true)}
                    className="px-4 py-2 rounded-xl bg-gray-100 hover:bg-gray-200 text-sm font-medium"
                  >
                    Change
                  </button>
                </div>
              ) : (
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <input
                      className="input-field pr-10"
                      type={showKey ? 'text' : 'password'}
                      value={newApiKey}
                      onChange={(e) => setNewApiKey(e.target.value)}
                      placeholder="Paste your API key..."
                      autoFocus
                    />
                    <button
                      type="button"
                      onClick={() => setShowKey(!showKey)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400"
                    >
                      {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                  <button
                    onClick={() => { setApiKeyEditing(false); setNewApiKey('') }}
                    className="px-4 py-2 rounded-xl bg-gray-100 text-sm"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>

            {settings.llm_provider === 'custom' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Base URL</label>
                <input
                  className="input-field"
                  value={settings.llm_base_url}
                  onChange={(e) => setSettings({ ...settings, llm_base_url: e.target.value })}
                  placeholder="http://localhost:11434/v1"
                />
              </div>
            )}

            {/* Test */}
            <div className="flex items-center gap-3 pt-1">
              <button onClick={handleTest} disabled={testing} className="btn-secondary flex items-center gap-2 text-sm">
                <TestTube2 size={16} />
                {testing ? 'Testing...' : 'Test Connection'}
              </button>
              {testResult && (
                <div className={`flex items-center gap-2 text-sm font-medium ${testResult.success ? 'text-green-600' : 'text-red-500'}`}>
                  {testResult.success ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                  {testResult.message}
                  {testResult.latency_ms && ` (${testResult.latency_ms}ms)`}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* OCR Config */}
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">📷 Handwriting Recognition (OCR)</h2>
          <div className="space-y-3">
            {[
              { value: 'local', label: 'Local (Tesseract)', desc: 'Fast, offline, less accurate for handwriting' },
              { value: 'vision_api', label: 'AI Vision', desc: "Uses your LLM's vision model — most accurate" },
              { value: 'hybrid', label: 'Hybrid (Recommended)', desc: 'Try local first, fall back to AI vision if unclear' },
            ].map((opt) => (
              <label key={opt.value} className={`flex items-start gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all ${settings.ocr_mode === opt.value ? 'border-primary-500 bg-primary-50' : 'border-gray-100 hover:border-gray-200'}`}>
                <input
                  type="radio"
                  name="ocr_mode"
                  value={opt.value}
                  checked={settings.ocr_mode === opt.value}
                  onChange={() => setSettings({ ...settings, ocr_mode: opt.value })}
                  className="mt-1 accent-primary-500"
                />
                <div>
                  <div className="font-medium text-gray-800">{opt.label}</div>
                  <div className="text-sm text-gray-500">{opt.desc}</div>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Network */}
        <div className="card">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2"><Wifi size={20} /> Network & iPad Access</h2>
          {networkInfo && (
            <div className="space-y-3">
              <div className="bg-primary-50 rounded-xl p-4">
                <p className="text-sm text-gray-600 mb-1">Open this URL on your iPad:</p>
                <p className="font-mono text-primary-700 font-bold text-lg">{networkInfo.access_url}</p>
              </div>
              <p className="text-sm text-gray-500">{networkInfo.ipad_instructions}</p>
              <div className="flex gap-4 text-sm text-gray-500">
                <span>Host: <strong>{networkInfo.hostname}</strong></span>
                <span>Port: <strong>{networkInfo.port}</strong></span>
              </div>
              <div className="bg-amber-50 rounded-xl p-3 text-sm text-amber-700">
                💡 Make sure both devices are on the same Wi-Fi network.
                If iPad can't connect, add a Windows Firewall rule for port 8000.
              </div>
            </div>
          )}

          <div className="mt-4 flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.lan_only_mode === '1'}
                onChange={(e) => setSettings({ ...settings, lan_only_mode: e.target.checked ? '1' : '0' })}
                className="w-4 h-4 accent-primary-500"
              />
              <span className="text-sm font-medium text-gray-700">Restrict to home network only</span>
            </label>
          </div>
        </div>

        {/* Save button */}
        <button onClick={handleSave} disabled={saving} className="btn-primary flex items-center gap-2">
          <Save size={18} />
          {saving ? 'Saving...' : saved ? '✓ Saved!' : 'Save Settings'}
        </button>
      </div>
    </Layout>
  )
}
