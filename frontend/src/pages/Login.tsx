import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, User } from '../api'
import { useAuthStore } from '../store/authStore'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { setAuth } = useAuthStore()
  const nav = useNavigate()

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await api.post<{ token: string; user: User }>('/auth/login', { username, password })
      setAuth(res.token, res.user)
      nav('/', { replace: true })
    } catch (err: any) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center">
      <form onSubmit={submit} className="w-80 space-y-4">
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold text-accent tracking-widest">STRAT-OS</h1>
          <p className="text-gray-400 text-sm mt-1">EV Kart Race Engineering</p>
        </div>

        {error && (
          <div className="bg-red bg-opacity-20 border border-red rounded px-3 py-2 text-sm text-red">
            {error}
          </div>
        )}

        <div>
          <label className="block text-xs text-gray-400 mb-1">Username</label>
          <input
            type="text"
            value={username}
            onChange={e => setUsername(e.target.value)}
            required
            className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent"
          />
        </div>

        <div>
          <label className="block text-xs text-gray-400 mb-1">Password</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            className="w-full bg-surface border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2 bg-accent text-bg font-bold rounded hover:opacity-90 disabled:opacity-50 transition"
        >
          {loading ? 'Signing in...' : 'Sign In'}
        </button>
      </form>
    </div>
  )
}
