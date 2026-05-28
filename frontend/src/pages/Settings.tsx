import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { authApi, type APIKeyResponse } from '@/lib/api'

type Provider = 'openai' | 'pinecone' | 'tavily'

const PROVIDERS: { id: Provider; label: string; description: string; docsUrl: string }[] = [
  {
    id: 'openai',
    label: 'OpenAI',
    description: 'Used for GPT-4o LLM calls and text-embedding-3-small embeddings.',
    docsUrl: 'https://platform.openai.com/api-keys',
  },
  {
    id: 'pinecone',
    label: 'Pinecone',
    description: 'Vector database for hybrid BM25 + dense retrieval.',
    docsUrl: 'https://app.pinecone.io',
  },
  {
    id: 'tavily',
    label: 'Tavily',
    description: 'Web search tool used by the insight and gap detection agents.',
    docsUrl: 'https://app.tavily.com',
  },
]

export default function Settings() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  // Saved keys from DB (hints only)
  const [savedKeys, setSavedKeys] = useState<Record<Provider, APIKeyResponse | null>>({
    openai: null, pinecone: null, tavily: null,
  })
  const [loadingKeys, setLoadingKeys] = useState(true)

  // Per-provider input state
  const [inputs, setInputs] = useState<Record<Provider, string>>({
    openai: '', pinecone: '', tavily: '',
  })
  const [showKey, setShowKey] = useState<Record<Provider, boolean>>({
    openai: false, pinecone: false, tavily: false,
  })
  const [saving, setSaving] = useState<Record<Provider, boolean>>({
    openai: false, pinecone: false, tavily: false,
  })
  const [deleting, setDeleting] = useState<Record<Provider, boolean>>({
    openai: false, pinecone: false, tavily: false,
  })
  const [feedback, setFeedback] = useState<Record<Provider, { type: 'success' | 'error'; msg: string } | null>>({
    openai: null, pinecone: null, tavily: null,
  })

  // ── Load saved keys on mount ─────────────────────────────────────────
  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await authApi.listKeys()
        const map: Record<Provider, APIKeyResponse | null> = {
          openai: null, pinecone: null, tavily: null,
        }
        data.forEach(k => {
          if (k.provider in map) {
            map[k.provider as Provider] = k
          }
        })
        setSavedKeys(map)
      } catch {
        // Non-fatal — show empty state
      } finally {
        setLoadingKeys(false)
      }
    }
    load()
  }, [])

  // ── Helpers ──────────────────────────────────────────────────────────
  const setFeedbackFor = (
    provider: Provider,
    type: 'success' | 'error',
    msg: string,
  ) => {
    setFeedback(f => ({ ...f, [provider]: { type, msg } }))
    setTimeout(
      () => setFeedback(f => ({ ...f, [provider]: null })),
      4000,
    )
  }

  // ── Save key ─────────────────────────────────────────────────────────
  const handleSave = async (provider: Provider) => {
    const key = inputs[provider].trim()
    if (!key) return

    setSaving(s => ({ ...s, [provider]: true }))
    try {
      const { data } = await authApi.addKey(provider, key)
      setSavedKeys(k => ({ ...k, [provider]: data }))
      setInputs(i => ({ ...i, [provider]: '' }))
      setFeedbackFor(provider, 'success', `Saved · hint: ${data.key_hint}`)
    } catch (err: any) {
      setFeedbackFor(
        provider,
        'error',
        err?.response?.data?.detail || 'Failed to save key.',
      )
    } finally {
      setSaving(s => ({ ...s, [provider]: false }))
    }
  }

  // ── Delete key ────────────────────────────────────────────────────────
  const handleDelete = async (provider: Provider) => {
    setDeleting(d => ({ ...d, [provider]: true }))
    try {
      await authApi.deleteKey(provider)
      setSavedKeys(k => ({ ...k, [provider]: null }))
      setFeedbackFor(provider, 'success', 'Key removed.')
    } catch (err: any) {
      setFeedbackFor(
        provider,
        'error',
        err?.response?.data?.detail || 'Failed to delete key.',
      )
    } finally {
      setDeleting(d => ({ ...d, [provider]: false }))
    }
  }

  return (
    <>
      <style>{settingsCss}</style>
      <div className="settings-root">

        {/* ── Topbar ── */}
        <div className="settings-topbar">
          <div className="settings-topbar-left">
            <button className="back-link" onClick={() => navigate('/')}>
              ← Dashboard
            </button>
            <div className="settings-title">
              Settings
              <span className="settings-title-sub">/ API Keys</span>
            </div>
          </div>
          <button className="logout-btn" onClick={logout}>
            Sign out
          </button>
        </div>

        {/* ── Body ── */}
        <div className="settings-body">

          {/* Left column — profile + info */}
          <div className="settings-left">
            <div className="profile-card">
              <div className="profile-avatar">
                {user?.email?.[0]?.toUpperCase() ?? 'U'}
              </div>
              <div className="profile-name">
                {user?.email?.split('@')[0]}
              </div>
              <div className="profile-email">{user?.email}</div>
              <div className="profile-status">
                <div className="status-dot" />
                <span>Active account</span>
              </div>
            </div>

            <div className="info-card">
              <div className="info-card-title">🔒 Security</div>
              <div className="info-list">
                {[
                  'Keys encrypted with Fernet (AES-128-CBC)',
                  'HMAC-SHA256 authentication on all tokens',
                  'Only key hints stored in the database',
                  'Per-user isolated namespaces in Pinecone',
                  'JWT access tokens expire in 15 minutes',
                ].map(item => (
                  <div key={item} className="info-item">
                    <span className="info-dot" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="info-card">
              <div className="info-card-title">📋 Key Status</div>
              <div className="key-status-list">
                {PROVIDERS.map(p => (
                  <div key={p.id} className="key-status-row">
                    <span className="key-status-label">{p.label}</span>
                    {loadingKeys ? (
                      <span className="key-badge loading">...</span>
                    ) : savedKeys[p.id] ? (
                      <span className="key-badge saved">
                        {savedKeys[p.id]!.key_hint}
                      </span>
                    ) : (
                      <span className="key-badge missing">not set</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right column — key management */}
          <div className="settings-right">
            <div className="section-header">
              <h2 className="section-title">API Key Management</h2>
              <p className="section-sub">
                Your keys are Fernet-encrypted before storage.
                The plain key is never saved — only the last 4 characters
                as a display hint.
              </p>
            </div>

            {PROVIDERS.map(provider => (
              <div key={provider.id} className="provider-card">
                <div className="provider-card-header">
                  <div className="provider-info">
                    <div className="provider-name">{provider.label}</div>
                    <div className="provider-desc">{provider.description}</div>
                  </div>
                  <div className="provider-header-right">
                    {!loadingKeys && savedKeys[provider.id] && (
                      <div className="provider-saved-badge">
                        <span className="saved-dot" />
                        {savedKeys[provider.id]!.key_hint}
                      </div>
                    )}
                    {!loadingKeys && !savedKeys[provider.id] && (
                      <div className="provider-missing-badge">not set</div>
                    )}
                    <a
                      href={provider.docsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="docs-link"
                    >
                      Get key ↗
                    </a>
                  </div>
                </div>

                <div className="provider-card-body">
                  {/* Input */}
                  <div className="key-input-group">
                    <div className="key-input-wrap">
                      <input
                        className="key-input"
                        type={showKey[provider.id] ? 'text' : 'password'}
                        placeholder={
                          savedKeys[provider.id]
                            ? `Update key (current: ${savedKeys[provider.id]!.key_hint})`
                            : `Paste your ${provider.label} API key...`
                        }
                        value={inputs[provider.id]}
                        onChange={e => setInputs(i => ({
                          ...i, [provider.id]: e.target.value,
                        }))}
                        onKeyDown={e => {
                          if (e.key === 'Enter') handleSave(provider.id)
                        }}
                      />
                      <span
                        className="key-eye"
                        onClick={() => setShowKey(s => ({
                          ...s, [provider.id]: !s[provider.id],
                        }))}
                      >
                        {showKey[provider.id] ? '🙈' : '👁'}
                      </span>
                    </div>

                    <div className="key-actions">
                      <button
                        className="save-btn"
                        onClick={() => handleSave(provider.id)}
                        disabled={!inputs[provider.id].trim() || saving[provider.id]}
                        style={{
                          opacity: !inputs[provider.id].trim() || saving[provider.id]
                            ? 0.5 : 1,
                          cursor: !inputs[provider.id].trim() || saving[provider.id]
                            ? 'not-allowed' : 'pointer',
                        }}
                      >
                        {saving[provider.id] ? 'Saving...' : 'Save'}
                      </button>

                      {savedKeys[provider.id] && (
                        <button
                          className="delete-btn"
                          onClick={() => handleDelete(provider.id)}
                          disabled={deleting[provider.id]}
                          style={{ opacity: deleting[provider.id] ? 0.5 : 1 }}
                        >
                          {deleting[provider.id] ? 'Removing...' : 'Remove'}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Feedback */}
                  {feedback[provider.id] && (
                    <div className={`key-feedback ${feedback[provider.id]!.type}`}>
                      {feedback[provider.id]!.type === 'success' ? '✓' : '⚠'}{' '}
                      {feedback[provider.id]!.msg}
                    </div>
                  )}
                </div>
              </div>
            ))}

          </div>
        </div>
      </div>
    </>
  )
}

const settingsCss = `
  .settings-root {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
    font-family: 'DM Sans', sans-serif;
    background: var(--bg);
  }
  .settings-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 28px;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
    flex-shrink: 0;
  }
  .settings-topbar-left {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .back-link {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: var(--text-muted);
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 0;
    transition: color 0.15s;
  }
  .back-link:hover { color: var(--accent); }
  .settings-title {
    font-family: 'DM Serif Display', serif;
    font-size: 18px;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .settings-title-sub {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    color: var(--text-muted);
  }
  .logout-btn {
    padding: 7px 16px;
    border: 1px solid var(--border);
    border-radius: 7px;
    background: transparent;
    font-family: 'DM Sans', sans-serif;
    font-size: 12px;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s;
  }
  .logout-btn:hover {
    color: var(--accent-warm);
    border-color: var(--accent-warm);
  }
  .settings-body {
    flex: 1;
    display: flex;
    gap: 24px;
    padding: 28px;
    overflow-y: auto;
    align-items: flex-start;
  }

  /* ── Left column ── */
  .settings-left {
    width: 240px;
    min-width: 240px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .profile-card {
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 4px;
  }
  .profile-avatar {
    width: 52px; height: 52px;
    border-radius: 50%;
    background: var(--accent);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'DM Serif Display', serif;
    font-size: 20px;
    margin-bottom: 8px;
  }
  .profile-name {
    font-family: 'DM Serif Display', serif;
    font-size: 16px;
    color: var(--text-primary);
  }
  .profile-email {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    color: var(--text-muted);
    margin-bottom: 10px;
  }
  .profile-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    color: #2e7d32;
  }
  .status-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: #4caf50;
  }
  .info-card {
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
  }
  .info-card-title {
    font-family: 'DM Serif Display', serif;
    font-size: 14px;
    color: var(--text-primary);
    margin-bottom: 12px;
  }
  .info-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .info-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    font-size: 11px;
    color: var(--text-secondary);
    line-height: 1.5;
  }
  .info-dot {
    width: 4px; height: 4px;
    border-radius: 50%;
    background: var(--accent-warm);
    flex-shrink: 0;
    margin-top: 6px;
  }
  .key-status-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .key-status-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .key-status-label {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: var(--text-secondary);
  }
  .key-badge {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    padding: 2px 8px;
    border-radius: 10px;
  }
  .key-badge.saved { background: #e8f5e9; color: #2e7d32; }
  .key-badge.missing { background: #fce4ec; color: #c62828; }
  .key-badge.loading { background: var(--tag-bg); color: var(--text-muted); }

  /* ── Right column ── */
  .settings-right {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 16px;
    min-width: 0;
  }
  .section-header {
    margin-bottom: 4px;
  }
  .section-title {
    font-family: 'DM Serif Display', serif;
    font-size: 22px;
    color: var(--text-primary);
    margin-bottom: 6px;
  }
  .section-sub {
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.6;
    font-family: 'DM Mono', monospace;
    max-width: 540px;
  }
  .provider-card {
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    transition: border-color 0.15s;
  }
  .provider-card:hover { border-color: #ccc9c2; }
  .provider-card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
    gap: 12px;
  }
  .provider-info { flex: 1; min-width: 0; }
  .provider-name {
    font-family: 'DM Serif Display', serif;
    font-size: 16px;
    color: var(--text-primary);
    margin-bottom: 3px;
  }
  .provider-desc {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.5;
    font-family: 'DM Mono', monospace;
  }
  .provider-header-right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  .provider-saved-badge {
    display: flex;
    align-items: center;
    gap: 5px;
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    color: #2e7d32;
    background: #e8f5e9;
    border: 1px solid #a5d6a7;
    padding: 3px 9px;
    border-radius: 10px;
  }
  .saved-dot {
    width: 5px; height: 5px;
    border-radius: 50%;
    background: #4caf50;
  }
  .provider-missing-badge {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    color: #c62828;
    background: #fce4ec;
    border: 1px solid #f48fb1;
    padding: 3px 9px;
    border-radius: 10px;
  }
  .docs-link {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    color: var(--accent-warm);
    text-decoration: none;
    padding: 3px 9px;
    border: 1px solid currentColor;
    border-radius: 10px;
    transition: opacity 0.15s;
  }
  .docs-link:hover { opacity: 0.75; }
  .provider-card-body {
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .key-input-group {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .key-input-wrap {
    flex: 1;
    position: relative;
  }
  .key-input {
    width: 100%;
    padding: 10px 36px 10px 12px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg);
    font-family: 'DM Mono', monospace;
    font-size: 12px;
    color: var(--text-primary);
    outline: none;
    transition: border-color 0.15s;
  }
  .key-input:focus { border-color: var(--accent); }
  .key-eye {
    position: absolute;
    right: 10px; top: 50%;
    transform: translateY(-50%);
    cursor: pointer; font-size: 13px;
    color: var(--text-muted);
    user-select: none;
  }
  .key-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }
  .save-btn {
    padding: 10px 18px;
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-family: 'DM Sans', sans-serif;
    font-size: 12px;
    font-weight: 500;
    transition: opacity 0.15s;
    white-space: nowrap;
  }
  .save-btn:hover { opacity: 0.85; }
  .delete-btn {
    padding: 10px 14px;
    background: transparent;
    color: #c62828;
    border: 1px solid #f48fb1;
    border-radius: 8px;
    font-family: 'DM Sans', sans-serif;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }
  .delete-btn:hover { background: #fce4ec; }
  .key-feedback {
    padding: 8px 12px;
    border-radius: 6px;
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    animation: fadeIn 0.2s ease;
  }
  .key-feedback.success {
    background: #e8f5e9;
    border: 1px solid #a5d6a7;
    color: #2e7d32;
  }
  .key-feedback.error {
    background: #fce4ec;
    border: 1px solid #f48fb1;
    color: #c62828;
  }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(-4px); }
    to   { opacity: 1; transform: translateY(0); }
  }
`