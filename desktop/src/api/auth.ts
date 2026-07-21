import { api } from './client'

export type FeatureFlags = {
  auth: boolean
  cloudSync: boolean
}

export type AuthState = {
  enabled: boolean
  loggedIn: boolean
  username?: string
  tokenMask?: string
  loggedInAt?: string
  features: FeatureFlags
}

export const authApi = {
  get() {
    return api.get<AuthState>('/api/auth')
  },

  login(username: string, password: string) {
    return api.post<{ ok: true } & AuthState>('/api/auth/login', { username, password })
  },

  logout() {
    return api.post<{ ok: true } & AuthState>('/api/auth/logout')
  },

  setFeatures(update: Partial<FeatureFlags>) {
    return api.put<{ ok: true } & AuthState>('/api/auth/features', update)
  },
}
