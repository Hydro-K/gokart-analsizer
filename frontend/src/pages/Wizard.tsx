import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, User } from '../api'
import { useAuthStore } from '../store/authStore'

type Step = 'welcome' | 'admin' | 'driver' | 'kart' | 'storage' | 'done'

export default function Wizard() {
  const [step, setStep] = useState<Step>('welcome')
  const [adminForm, setAdminForm] = useState({ username: '', display_name: '', password: '' })
  const [driverName, setDriverName] = useState('')
  const [kartName, setKartName] = useState('')
  const [error, setError] = useState('')
  const { setAuth } = useAuthStore()
  const nav = useNavigate()

  const createAdmin = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      const res = await api.post<{ token: string; user: User }>('/auth/register', {
        ...adminForm, role: 'admin'
      })
      setAuth(res.token, res.user)
      setStep('driver')
    } catch (err: any) {
      setError(err.message)
    }
  }

  const createDriver = async (e: FormEvent) => {
    e.preventDefault()
    if (driverName.trim()) {
      try { await api.post('/drivers', { name: driverName.trim(), notes: '' }) } catch { /* ok */ }
    }
    setStep('kart')
  }

  const createKart = async (e: FormEvent) => {
    e.preventDefault()
    if (kartName.trim()) {
      try { await api.post('/karts', { name: kartName.trim() }) } catch { /* ok */ }
    }
    setStep('storage')
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center">
      <div className="w-96 space-y-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-accent tracking-widest">STRAT-OS</h1>
          <p className="text-gray-400 text-sm mt-1">First Boot Setup</p>
        </div>

        {/* Progress */}
        <div className="flex gap-1">
          {(['welcome','admin','driver','kart','storage','done'] as Step[]).map((s, i) => (
            <div key={s} className={`flex-1 h-1 rounded-full ${
              ['welcome','admin','driver','kart','storage','done'].indexOf(step) >= i ? 'bg-accent' : 'bg-border'
            }`} />
          ))}
        </div>

        {step === 'welcome' && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-white">Welcome to Strat-OS</h2>
            <p className="text-gray-300 text-sm">
              Strat-OS is your offline race engineering platform for EV karts. This wizard
              will configure your system. All data stays on-device — no internet required.
            </p>
            <ul className="text-sm text-gray-400 space-y-1 list-disc list-inside">
              <li>Create admin account</li>
              <li>Add first driver</li>
              <li>Configure kart (220A EVGP cap enforced)</li>
              <li>Storage settings</li>
            </ul>
            <button onClick={() => setStep('admin')} className="w-full py-2 bg-accent text-bg font-bold rounded hover:opacity-90">
              Get Started
            </button>
          </div>
        )}

        {step === 'admin' && (
          <form onSubmit={createAdmin} className="space-y-3">
            <h2 className="text-xl font-bold text-white">Create Admin Account</h2>
            {error && <div className="text-red text-sm">{error}</div>}
            <input placeholder="Username" required value={adminForm.username}
              onChange={e => setAdminForm(f => ({ ...f, username: e.target.value }))}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            <input placeholder="Display name" required value={adminForm.display_name}
              onChange={e => setAdminForm(f => ({ ...f, display_name: e.target.value }))}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            <input type="password" placeholder="Password" required value={adminForm.password}
              onChange={e => setAdminForm(f => ({ ...f, password: e.target.value }))}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            <button type="submit" className="w-full py-2 bg-accent text-bg font-bold rounded hover:opacity-90">
              Create Account
            </button>
          </form>
        )}

        {step === 'driver' && (
          <form onSubmit={createDriver} className="space-y-3">
            <h2 className="text-xl font-bold text-white">Add First Driver</h2>
            <p className="text-gray-400 text-sm">Drivers are people who drive the kart (linked to lap data).</p>
            <input placeholder="Driver name" value={driverName} onChange={e => setDriverName(e.target.value)}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            <div className="flex gap-2">
              <button type="button" onClick={() => setStep('kart')} className="flex-1 py-2 border border-border rounded text-gray-400 hover:border-white hover:text-white">
                Skip
              </button>
              <button type="submit" className="flex-1 py-2 bg-accent text-bg font-bold rounded hover:opacity-90">
                {driverName.trim() ? 'Add & Continue' : 'Skip'}
              </button>
            </div>
          </form>
        )}

        {step === 'kart' && (
          <form onSubmit={createKart} className="space-y-3">
            <h2 className="text-xl font-bold text-white">Configure Kart</h2>
            <p className="text-gray-400 text-sm">Max controller current is capped at <span className="text-orange font-bold">220A</span> (EVGP rule).</p>
            <input placeholder="Kart name (e.g. Kart #7)" value={kartName} onChange={e => setKartName(e.target.value)}
              className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
            <div className="flex gap-2">
              <button type="button" onClick={() => setStep('storage')} className="flex-1 py-2 border border-border rounded text-gray-400 hover:border-white hover:text-white">
                Skip
              </button>
              <button type="submit" className="flex-1 py-2 bg-accent text-bg font-bold rounded hover:opacity-90">
                {kartName.trim() ? 'Add & Continue' : 'Skip'}
              </button>
            </div>
          </form>
        )}

        {step === 'storage' && (
          <div className="space-y-3">
            <h2 className="text-xl font-bold text-white">Storage</h2>
            <p className="text-gray-400 text-sm">
              Archive tier can be configured later in Settings. Options: SMB network share,
              Google Drive (via rclone), or disabled.
            </p>
            <p className="text-gray-400 text-sm">
              Auto-cleanup triggers at <span className="text-gold">70%</span> warn,{' '}
              <span className="text-orange">80%</span> archive, and{' '}
              <span className="text-red">90%</span> emergency delete.
            </p>
            <button onClick={() => setStep('done')} className="w-full py-2 bg-accent text-bg font-bold rounded hover:opacity-90">
              Continue
            </button>
          </div>
        )}

        {step === 'done' && (
          <div className="space-y-4 text-center">
            <div className="text-5xl">✓</div>
            <h2 className="text-xl font-bold text-white">Strat-OS Ready</h2>
            <p className="text-gray-400 text-sm">Upload your first AiM CSV session to get started.</p>
            <button onClick={() => window.location.replace('/')} className="w-full py-2 bg-accent text-bg font-bold rounded hover:opacity-90">
              Go to Dashboard
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
