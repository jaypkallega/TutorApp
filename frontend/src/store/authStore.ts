import { create } from 'zustand'

export interface AuthUser {
  user_id: number
  display_name: string
  role: 'parent' | 'child'
  access_token: string
}

interface AuthState {
  user: AuthUser | null
  setUser: (user: AuthUser) => void
  logout: () => void
  isParent: () => boolean
  isChild: () => boolean
}

// Restore from sessionStorage on load
function loadStoredUser(): AuthUser | null {
  try {
    const stored = sessionStorage.getItem('user')
    const token = sessionStorage.getItem('token')
    if (stored && token) {
      const user = JSON.parse(stored) as AuthUser
      return { ...user, access_token: token }
    }
  } catch {
    // ignore
  }
  return null
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: loadStoredUser(),

  setUser: (user) => {
    sessionStorage.setItem('token', user.access_token)
    sessionStorage.setItem('user', JSON.stringify(user))
    set({ user })
  },

  logout: () => {
    sessionStorage.removeItem('token')
    sessionStorage.removeItem('user')
    set({ user: null })
  },

  isParent: () => get().user?.role === 'parent',
  isChild: () => get().user?.role === 'child',
}))
