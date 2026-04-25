import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { User } from '../api'

interface AuthStore {
  token: string | null
  user: User | null
  setAuth: (token: string, user: User) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setAuth: (token, user) => {
        localStorage.setItem('stratos_token', token)
        set({ token, user })
      },
      clearAuth: () => {
        localStorage.removeItem('stratos_token')
        set({ token: null, user: null })
      },
    }),
    { name: 'stratos-auth', partialize: (s) => ({ token: s.token, user: s.user }) }
  )
)
