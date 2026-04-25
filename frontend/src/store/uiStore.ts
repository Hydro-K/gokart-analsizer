import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Mode = 'beginner' | 'engineer'

interface UIStore {
  mode: Mode
  toggleMode: () => void
  sidebarOpen: boolean
  setSidebarOpen: (v: boolean) => void
}

export const useUIStore = create<UIStore>()(
  persist(
    (set, get) => ({
      mode: 'engineer',
      toggleMode: () => set({ mode: get().mode === 'engineer' ? 'beginner' : 'engineer' }),
      sidebarOpen: true,
      setSidebarOpen: (v) => set({ sidebarOpen: v }),
    }),
    { name: 'stratos-ui' }
  )
)
