import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react'
import { authApi, tokenStorage, type UserResponse } from '@/lib/api'

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface AuthState {
  user: UserResponse | null
  isAuthenticated: boolean
  isLoading: boolean        // true during initial session restore
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
}

// ─────────────────────────────────────────────────────────────────────────────
// Context
// ─────────────────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null)

// ─────────────────────────────────────────────────────────────────────────────
// Provider
// ─────────────────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,      // start true — restoring session
  })

  // ── Session restore on mount ─────────────────────────────────────────
  // On page refresh the access token (in memory) is lost.
  // If a refresh token exists in sessionStorage, silently get a new
  // access token and load the user — seamless re-auth.
  useEffect(() => {
    const restoreSession = async () => {
      const refreshToken = tokenStorage.getRefresh()

      if (!refreshToken) {
        setState(s => ({ ...s, isLoading: false }))
        return
      }

      try {
        const { data } = await authApi.refresh(refreshToken)
        tokenStorage.setAccess(data.access_token)
        tokenStorage.setRefresh(data.refresh_token)

        const { data: user } = await authApi.me()
        setState({ user, isAuthenticated: true, isLoading: false })

      } catch {
        // Refresh token expired or invalid — clear and show login
        tokenStorage.clearAll()
        setState({ user: null, isAuthenticated: false, isLoading: false })
      }
    }

    restoreSession()
  }, [])

  // ── Login ────────────────────────────────────────────────────────────
  const login = useCallback(async (email: string, password: string) => {
    const { data: tokens } = await authApi.login(email, password)
    tokenStorage.setAccess(tokens.access_token)
    tokenStorage.setRefresh(tokens.refresh_token)

    const { data: user } = await authApi.me()
    setState({ user, isAuthenticated: true, isLoading: false })
  }, [])

  // ── Register ─────────────────────────────────────────────────────────
  const register = useCallback(async (email: string, password: string) => {
    const { data: tokens } = await authApi.register(email, password)
    tokenStorage.setAccess(tokens.access_token)
    tokenStorage.setRefresh(tokens.refresh_token)

    const { data: user } = await authApi.me()
    setState({ user, isAuthenticated: true, isLoading: false })
  }, [])

  // ── Logout ───────────────────────────────────────────────────────────
  const logout = useCallback(() => {
    tokenStorage.clearAll()
    setState({ user: null, isAuthenticated: false, isLoading: false })
    window.location.href = '/login'
  }, [])

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Hook
// ─────────────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}