import { NavLink } from 'react-router-dom'
import { useUIStore } from '../../store/uiStore'
import { useAuthStore } from '../../store/authStore'

const NAV = [
  { to: '/',              label: 'Dashboard' },
  { to: '/sessions',      label: 'Sessions' },
  { to: '/upload',        label: 'Upload' },
  { to: '/drivers',       label: 'Drivers' },
  { to: '/karts',         label: 'Karts' },
  { to: '/tracks',        label: 'Tracks' },
  { to: '/simulation',    label: 'Simulation',   engineer: true },
  { to: '/ml',            label: 'ML Analysis',  engineer: true },
  { to: '/evolution',     label: 'Driver Evo',   engineer: true },
  { to: '/compare',       label: 'Compare',      engineer: true },
  { to: '/compliance',    label: 'Compliance' },
  { to: '/storage',       label: 'Storage',      engineer: true },
  { to: '/users',         label: 'Users',        admin: true },
  { to: '/settings',      label: 'Settings' },
  { to: '/pi-guide',      label: 'Pi Setup' },
]

export function Sidebar() {
  const { mode, toggleMode } = useUIStore()
  const { user, clearAuth } = useAuthStore()

  return (
    <aside className="w-48 min-h-screen bg-surface border-r border-border flex flex-col">
      <div className="px-4 py-5 border-b border-border">
        <span className="text-accent font-bold text-lg tracking-widest">STRAT-OS</span>
      </div>

      <nav className="flex-1 py-2 overflow-y-auto">
        {NAV.filter(n => {
          if (n.admin && user?.role !== 'admin') return false
          if (n.engineer && mode === 'beginner') return false
          return true
        }).map(n => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === '/'}
            className={({ isActive }) =>
              `block px-4 py-2 text-sm transition-colors ${
                isActive ? 'text-accent bg-border' : 'text-gray-300 hover:text-white hover:bg-border'
              }`
            }
          >
            {n.label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border p-3 space-y-2">
        <button
          onClick={toggleMode}
          className="w-full text-xs px-2 py-1 rounded bg-border hover:bg-accent hover:text-bg transition-colors"
        >
          Mode: {mode === 'engineer' ? 'Engineer' : 'Beginner'}
        </button>
        <div className="text-xs text-gray-500 truncate px-1">{user?.display_name}</div>
        <button
          onClick={clearAuth}
          className="w-full text-xs px-2 py-1 rounded border border-border hover:border-red hover:text-red transition-colors"
        >
          Logout
        </button>
      </div>
    </aside>
  )
}
