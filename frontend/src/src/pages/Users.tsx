import { useEffect, useState, FormEvent } from 'react'
import { api, User } from '../api'
import { StatusBadge } from '../components/common/StatusBadge'
import { useAuthStore } from '../store/authStore'

export default function Users() {
  const [users, setUsers] = useState<User[]>([])
  const [form, setForm]   = useState({ username: '', display_name: '', password: '', role: 'engineer' })
  const [error, setError] = useState('')
  const currentUser = useAuthStore(s => s.user)

  const load = () => api.get<User[]>('/users').then(setUsers).catch(() => {})
  useEffect(() => { load() }, [])

  const create = async (e: FormEvent) => {
    e.preventDefault(); setError('')
    try {
      await api.post('/users', form)
      setForm({ username: '', display_name: '', password: '', role: 'engineer' })
      load()
    } catch (err: any) { setError(err.message) }
  }

  const del = async (id: number) => {
    if (id === currentUser?.id) { alert("Can't delete your own account"); return }
    if (!confirm('Delete user?')) return
    try { await api.delete(`/users/${id}`); load() }
    catch (err: any) { alert(err.message) }
  }

  const f = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(prev => ({ ...prev, [k]: e.target.value }))

  const ROLE_STATUS: Record<string, string> = { admin: 'critical', engineer: 'done', viewer: 'ok' }

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-white">Users</h1>

      <form onSubmit={create} className="space-y-3 bg-surface border border-border rounded-lg p-4">
        <h2 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Create User</h2>
        {error && <div className="text-red text-sm">{error}</div>}
        <div className="grid grid-cols-2 gap-2">
          <input placeholder="Username" required value={form.username} onChange={f('username')}
            className="bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
          <input placeholder="Display name" required value={form.display_name} onChange={f('display_name')}
            className="bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
        </div>
        <input type="password" placeholder="Password" required value={form.password} onChange={f('password')}
          className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent" />
        <select value={form.role} onChange={f('role')}
          className="w-full bg-bg border border-border rounded px-3 py-2 text-white focus:outline-none focus:border-accent">
          <option value="admin">Admin — full access</option>
          <option value="engineer">Engineer — upload &amp; edit sessions</option>
          <option value="viewer">Viewer — read only</option>
        </select>
        <button type="submit" className="px-4 py-2 bg-accent text-bg font-bold rounded hover:opacity-90 text-sm">
          Create User
        </button>
      </form>

      <div className="space-y-2">
        {users.map(u => (
          <div key={u.id} className="flex items-center gap-4 rounded-lg border border-border bg-surface px-4 py-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-white font-medium">{u.display_name}</span>
                {u.id === currentUser?.id && <span className="text-xs text-gray-500">(you)</span>}
              </div>
              <div className="text-xs text-gray-400 font-mono">{u.username}</div>
            </div>
            <StatusBadge status={ROLE_STATUS[u.role] ?? 'ok'} />
            <span className="text-xs text-gray-400 capitalize">{u.role}</span>
            {u.id !== currentUser?.id && (
              <button onClick={() => del(u.id)} className="text-xs text-gray-500 hover:text-red transition-colors ml-2">
                Delete
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
