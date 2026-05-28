import { useState} from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err: any) {
      setError(
        err?.response?.data?.detail || 'Invalid email or password.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.root}>
      <style>{animations}</style>

      {/* Left panel — branding */}
      <div style={styles.left}>
        <div style={styles.leftInner}>
          <div style={styles.logo}>
            <span style={styles.logoMark}>RC</span>
          </div>
          <h1 style={styles.brand}>Research<br />Copilot</h1>
          <p style={styles.brandSub}>
            Multi-agent AI system for automated research analysis,
            cross-paper synthesis, and gap detection.
          </p>
          <div style={styles.featureList}>
            {[
              'Hybrid BM25 + semantic retrieval',
              'LangGraph multi-agent pipeline',
              'MCP dynamic tool integration',
              'Per-user encrypted API keys',
            ].map(f => (
              <div key={f} style={styles.featureItem}>
                <span style={styles.featureDot} />
                <span style={styles.featureText}>{f}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel — form */}
      <div style={styles.right}>
        <div style={styles.formCard}>
          <div style={styles.formHeader}>
            <h2 style={styles.formTitle}>Sign in</h2>
            <p style={styles.formSub}>
              Don't have an account?{' '}
              <Link to="/register" style={styles.link}>Register</Link>
            </p>
          </div>

          <form onSubmit={handleSubmit} style={styles.form}>
            {/* Email */}
            <div style={styles.field}>
              <label style={styles.label}>Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                style={styles.input}
                onFocus={e => e.target.style.borderColor = 'var(--accent)'}
                onBlur={e => e.target.style.borderColor = 'var(--border)'}
              />
            </div>

            {/* Password */}
            <div style={styles.field}>
              <label style={styles.label}>Password</label>
              <div style={styles.inputWrap}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  style={{ ...styles.input, paddingRight: 40 }}
                  onFocus={e => e.target.style.borderColor = 'var(--accent)'}
                  onBlur={e => e.target.style.borderColor = 'var(--border)'}
                />
                <span
                  style={styles.eyeToggle}
                  onClick={() => setShowPassword(p => !p)}
                >
                  {showPassword ? '🙈' : '👁'}
                </span>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div style={styles.errorBox}>
                <span style={styles.errorIcon}>⚠</span> {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              style={{
                ...styles.submitBtn,
                opacity: loading ? 0.7 : 1,
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              {loading ? (
                <span style={styles.loadingRow}>
                  <span style={styles.spinner} /> signing in...
                </span>
              ) : 'Sign in →'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

const animations = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500;600&display=swap');
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
  }
`

const styles: Record<string, React.CSSProperties> = {
  root: {
    display: 'flex',
    height: '100vh',
    overflow: 'hidden',
    fontFamily: "'DM Sans', sans-serif",
  },
  left: {
    width: '45%',
    background: 'var(--accent)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '48px',
  },
  leftInner: {
    maxWidth: 360,
    animation: 'fadeUp 0.5s ease both',
  },
  logo: {
    width: 44,
    height: 44,
    borderRadius: 10,
    background: 'rgba(255,255,255,0.12)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  logoMark: {
    fontFamily: "'DM Serif Display', serif",
    fontSize: 18,
    color: '#fff',
    letterSpacing: '0.05em',
  },
  brand: {
    fontFamily: "'DM Serif Display', serif",
    fontSize: 40,
    color: '#fff',
    lineHeight: 1.15,
    marginBottom: 16,
  },
  brandSub: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.6)',
    lineHeight: 1.6,
    marginBottom: 32,
    fontFamily: "'DM Sans', sans-serif",
  },
  featureList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  featureItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  featureDot: {
    width: 5,
    height: 5,
    borderRadius: '50%',
    background: 'var(--accent-warm)',
    flexShrink: 0,
  },
  featureText: {
    fontFamily: "'DM Mono', monospace",
    fontSize: 11,
    color: 'rgba(255,255,255,0.7)',
    letterSpacing: '0.03em',
  },
  right: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '48px',
    background: 'var(--bg)',
  },
  formCard: {
    width: '100%',
    maxWidth: 380,
    animation: 'fadeUp 0.5s 0.1s ease both',
    opacity: 0,
  },
  formHeader: {
    marginBottom: 32,
  },
  formTitle: {
    fontFamily: "'DM Serif Display', serif",
    fontSize: 28,
    color: 'var(--text-primary)',
    marginBottom: 6,
  },
  formSub: {
    fontSize: 13,
    color: 'var(--text-muted)',
  },
  link: {
    color: 'var(--accent-warm)',
    textDecoration: 'none',
    fontWeight: 500,
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: 18,
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  label: {
    fontFamily: "'DM Mono', monospace",
    fontSize: 10,
    letterSpacing: '0.1em',
    textTransform: 'uppercase' as const,
    color: 'var(--text-muted)',
  },
  inputWrap: {
    position: 'relative',
  },
  input: {
    width: '100%',
    padding: '11px 14px',
    border: '1px solid var(--border)',
    borderRadius: 8,
    background: 'var(--panel-bg)',
    fontFamily: "'DM Sans', sans-serif",
    fontSize: 13,
    color: 'var(--text-primary)',
    outline: 'none',
    transition: 'border-color 0.15s',
  },
  eyeToggle: {
    position: 'absolute',
    right: 12,
    top: '50%',
    transform: 'translateY(-50%)',
    cursor: 'pointer',
    fontSize: 14,
    userSelect: 'none',
  },
  errorBox: {
    padding: '10px 14px',
    background: '#fce4ec',
    border: '1px solid #f48fb1',
    borderRadius: 7,
    fontSize: 12,
    color: '#c62828',
    fontFamily: "'DM Mono', monospace",
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  errorIcon: {
    fontSize: 14,
  },
  submitBtn: {
    padding: '12px',
    background: 'var(--accent)',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    fontFamily: "'DM Sans', sans-serif",
    fontSize: 14,
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'opacity 0.15s',
    marginTop: 4,
  },
  loadingRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  spinner: {
    display: 'inline-block',
    width: 14,
    height: 14,
    border: '2px solid rgba(255,255,255,0.3)',
    borderTop: '2px solid #fff',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
  },
}