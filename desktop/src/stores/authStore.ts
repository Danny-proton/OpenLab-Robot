import { create } from 'zustand'
import { authApi, type AuthState, type FeatureFlags } from '../api/auth'

type AuthStore = {
  enabled: boolean
  loggedIn: boolean
  username?: string
  tokenMask?: string
  loggedInAt?: string
  features: FeatureFlags
  loaded: boolean
  busy: boolean
  error?: string

  fetchState: () => Promise<void>
  login: (username: string, password: string) => Promise<boolean>
  logout: () => Promise<void>
  setFeatures: (update: Partial<FeatureFlags>) => Promise<void>
}

function applyState(state: AuthState) {
  return {
    enabled: state.enabled,
    loggedIn: state.loggedIn,
    username: state.username,
    tokenMask: state.tokenMask,
    loggedInAt: state.loggedInAt,
    features: state.features,
  }
}

export const useAuthStore = create<AuthStore>((set) => ({
  enabled: true,
  loggedIn: false,
  features: { auth: true, cloudSync: true },
  loaded: false,
  busy: false,

  fetchState: async () => {
    try {
      const state = await authApi.get()
      set({ ...applyState(state), loaded: true, error: undefined })
    } catch (err) {
      set({ loaded: true, error: err instanceof Error ? err.message : String(err) })
    }
  },

  login: async (username, password) => {
    set({ busy: true, error: undefined })
    try {
      const state = await authApi.login(username, password)
      set({ ...applyState(state), busy: false })
      return true
    } catch (err) {
      set({ busy: false, error: err instanceof Error ? err.message : String(err) })
      return false
    }
  },

  logout: async () => {
    set({ busy: true })
    try {
      const state = await authApi.logout()
      set({ ...applyState(state), busy: false })
    } catch (err) {
      set({ busy: false, error: err instanceof Error ? err.message : String(err) })
    }
  },

  setFeatures: async (update) => {
    try {
      const state = await authApi.setFeatures(update)
      set(applyState(state))
    } catch (err) {
      set({ error: err instanceof Error ? err.message : String(err) })
    }
  },
}))
