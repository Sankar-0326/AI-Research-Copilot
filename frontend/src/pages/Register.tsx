import { useState} from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')

    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)
    try {
      await register(email, password)
      navigate('/', { replace: true })
    } catch (err: any) {
      setError(
        err?.response?.data?.detail || 'Registration failed. Please try again.'
      )
    } finally {
      setLoading(false)
    }
  }

  // Password strength indicator
  const strength = (() => {
    if (!password) return 0
    let score = 0
    if (password.length >= 8) score++
    if (password.length >= 12) score++
    if (/[A-Z]/.test(password)) score++
    if (/[0-9]/.test(password)) score++
    if (/[^A-Za-z0-9]/.test(password)) score++
    return score
  })()

  const strengthLabel = ['', 'Weak', 'Fair', 'Good', 'Strong', 'Very strong']
  const strengthColor = ['', '#ef5350', '#ff9800', '#fdd835', '#66bb6a', '#43a047']

  return (
    <div style={styles.root}>
      <style>{animations}</style>

      {/* Left panel */}
      <div style={styles.left}>
        <div style={styles.leftInner}>
          <div style={styles.logo}>
            <span style={styles.logoMark}>RC</span>
          </div>
          <h1 style={styles.brand}>Start your<br />research<br /><em>journey.</em></h1>
          <p style={styles.brandSub}>
            Create an account and bring your own API keys.
            Your keys are Fernet-encrypted and never exposed.
          </p>
          <div style={styles.securityNote}>
            <span style={styles.securityIcon}>🔒</span>
            <span style={styles.securityText}>
              AES-128 encrypted · Zero plaintext storage · Per-user isolation
            </span>
          </div>
        </div>
      </div>

      {/* Right panel */}
      <div style={styles.right}>
        <div style={styles.formCard}>
          <div style={styles.formHeader}>
            <h2 style={styles.formTitle}>Create account</h2>
            <p style={styles.formSub}>
              Already have an account?{' '}
              <Link to="/login" style={styles.link}>Sign in</Link>
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
                  placeholder="min. 8 characters"
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

              {/* Strength meter */}
              {password && (
                <div style={styles.strengthWrap}>
                  <div style={styles.strengthTrack}>
                    {[1,2,3,4,5].map(i => (
                      <div
                        key={i}
                        style={{
                          ...styles.strengthSegment,
                          background: i <= strength
                            ? strengthColor[strength]
                            : 'var(--border)',
                        }}
                      />
                    ))}
                  </div>
                  <span style={{
                    ...styles.strengthLabel,
                    color: strengthColor[strength],
                  }}>
                    {strengthLabel[strength]}
                  </span>
                </div>
              )}
            </div>

            {/* Confirm password */}
            <div style={styles.field}>
              <label style={styles.label}>Confirm Password</label>
              <input
                type="password"
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                placeholder="••••••••"
                required
                style={{
                  ...styles.input,
                  borderColor: confirm && confirm !== password
                    ? '#ef5350'
                    : 'var(--border)',
                }}
                onFocus={e => e.target.style.borderColor =
                  confirm !== password ? '#ef5350' : 'var(--accent)'
                }
                onBlur={e => e.target.style.borderColor =
                  confirm && confirm !== password ? '#ef5350' : 'var(--border)'
                }
              />
              {confirm && confirm !== password && (
                <span style={styles.fieldError}>Passwords do not match</span>
              )}
            </div>

            {/* Error */}
            {error && (
              <div style={styles.errorBox}>
                <span>⚠</span> {error}
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
                  <span style={styles.spinner} /> creating account...
                </span>
              ) : 'Create account →'}
            </button>

            <p style={styles.terms}>
              By registering you agree that your API keys are stored
              encrypted and only you can access them.
            </p>
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
  },
  brand: {
    fontFamily: "'DM Serif Display', serif",
    fontSize: 40,
    color: '#fff',
    lineHeight: 1.2,
    marginBottom: 16,
  },
  brandSub: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.6)',
    lineHeight: 1.6,
    marginBottom: 24,
  },
  securityNote: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 10,
    padding: '12px 14px',
    background: 'rgba(255,255,255,0.07)',
    borderRadius: 8,
    border: '1px solid rgba(255,255,255,0.1)',
  },
  securityIcon: {
    fontSize: 14,
    flexShrink: 0,
  },
  securityText: {
    fontFamily: "'DM Mono', monospace",
    fontSize: 10,
    color: 'rgba(255,255,255,0.6)',
    lineHeight: 1.6,
    letterSpacing: '0.03em',
  },
  right: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '48px',
    background: 'var(--bg)',
    overflowY: 'auto',
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
  inputWrap: { position: 'relative' },
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
  strengthWrap: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginTop: 4,
  },
  strengthTrack: {
    flex: 1,
    display: 'flex',
    gap: 3,
  },
  strengthSegment: {
    flex: 1,
    height: 3,
    borderRadius: 2,
    transition: 'background 0.2s',
  },
  strengthLabel: {
    fontFamily: "'DM Mono', monospace",
    fontSize: 10,
    width: 60,
    textAlign: 'right' as const,
    transition: 'color 0.2s',
  },
  fieldError: {
    fontFamily: "'DM Mono', monospace",
    fontSize: 10,
    color: '#ef5350',
    marginTop: 2,
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
  submitBtn: {
    padding: '12px',
    background: 'var(--accent)',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    fontFamily: "'DM Sans', sans-serif",
    fontSize: 14,
    fontWeight: 500,
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
  terms: {
    fontSize: 11,
    color: 'var(--text-muted)',
    textAlign: 'center' as const,
    lineHeight: 1.5,
    fontFamily: "'DM Mono', monospace",
  },
}