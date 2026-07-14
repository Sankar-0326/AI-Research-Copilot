import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

// ─────────────────────────────────────────────────────────────────────────────
// Token storage
// Tokens live in memory only — never localStorage (XSS risk)
// Access token: short-lived, kept in memory
// Access token: short-lived, kept in memory only
// Refresh token: stored in httpOnly cookie (set by server, JS cannot read it)
// ─────────────────────────────────────────────────────────────────────────────

let accessToken: string | null = null

export const tokenStorage = {
  getAccess: () => accessToken,
  setAccess: (token: string) => { accessToken = token },
  clearAccess: () => { accessToken = null },

  clearAll: () => {
    accessToken = null
    // Refresh token lives in httpOnly cookie — cleared server-side via /auth/logout
  },
}

// ─────────────────────────────────────────────────────────────────────────────
// Axios instance
// ─────────────────────────────────────────────────────────────────────────────

export const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
  withCredentials: true,   // ← ensures cookies are sent with every request
})

// ─────────────────────────────────────────────────────────────────────────────
// Request interceptor — attach Bearer token to every request
// ─────────────────────────────────────────────────────────────────────────────

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = tokenStorage.getAccess()
    if (token && config.headers) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// ─────────────────────────────────────────────────────────────────────────────
// Response interceptor — auto-refresh on 401, retry original request
// ─────────────────────────────────────────────────────────────────────────────

let isRefreshing = false
let refreshQueue: Array<{
  resolve: (token: string) => void
  reject: (err: unknown) => void
}> = []

const processQueue = (error: unknown, token: string | null) => {
  refreshQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error)
    else resolve(token!)
  })
  refreshQueue = []
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean
    }

    // Only attempt refresh on 401 and only once per request
    if (
      error.response?.status !== 401 ||
      original._retry ||
      original.url?.includes('/auth/refresh')   // ← break the loop
    ) {
      return Promise.reject(error)
    }

    if (isRefreshing) {
      // Another request is already refreshing — queue this one
      return new Promise((resolve, reject) => {
        refreshQueue.push({ resolve, reject })
      }).then((token) => {
        original.headers['Authorization'] = `Bearer ${token}`
        return api(original)
      })
    }

    original._retry = true
    isRefreshing = true

    try {
      const { data } = await axios.post(
        '/api/auth/refresh',
        {},                    // ← empty body, cookie carries the token
        { withCredentials: true }
      )

      tokenStorage.setAccess(data.access_token)

      processQueue(null, data.access_token)

      original.headers['Authorization'] = `Bearer ${data.access_token}`
      return api(original)

    } catch (refreshError) {
      processQueue(refreshError, null)
      tokenStorage.clearAll()
      window.location.href = '/login'
      return Promise.reject(refreshError)

    } finally {
      isRefreshing = false
    }
  },
)

// ─────────────────────────────────────────────────────────────────────────────
// Typed API calls
// ─────────────────────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserResponse {
  id: string
  email: string
  is_active: boolean
}

export interface APIKeyResponse {
  id: string
  provider: string
  key_hint: string
  created_at: string
}

export interface UploadResponse {
  paper_id: string
  filename: string
  page_count: number
  chunks_stored: number
  status: string
}

export interface AnalyzeRequest {
  query: string
  paper_ids: string[]
  retrieval_mode: 'single' | 'cross' | 'hybrid'
}

export interface AnalyzeResponse {
  job_id: string
  status: string
  message: string
}

export interface FullReportResponse {
  job_id: string
  query: string
  paper_ids: string[]
  summaries: Record<string, string>
  insights: string[]
  research_gaps: string[]
  future_directions: string[]
  final_report: string
  completed_agents: string[]
  errors: string[]
  status: string
}

// Auth
export const authApi = {
  register: (email: string, password: string) =>
    api.post<TokenResponse>('/auth/register', { email, password }),

  login: (email: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { email, password }),

  me: () =>
    api.get<UserResponse>('/auth/me'),

  addKey: (provider: string, api_key: string) =>
    api.post<APIKeyResponse>('/auth/keys', { provider, api_key }),

  listKeys: () =>
    api.get<APIKeyResponse[]>('/auth/keys'),

  deleteKey: (provider: string) =>
    api.delete(`/auth/keys/${provider}`),

  logout: () => api.post('/auth/logout'),

  refresh: (_token: string) => api.post<TokenResponse>('/auth/refresh', {}, { withCredentials: true }),

}

// Papers
export const papersApi = {
  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<UploadResponse>('/papers/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  list: () =>
    api.get<{ namespaces: { id: string; name: string; vector_count: number }[] }>(
      '/papers/list'
    ),
}

// Analysis
export const analysisApi = {
  analyze: (payload: AnalyzeRequest) =>
    api.post<AnalyzeResponse>('/analysis/analyze', payload),

  getReport: (jobId: string) =>
    api.get<FullReportResponse>(`/analysis/report/${jobId}`),
}