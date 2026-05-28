import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { authApi } from '@/lib/api'

interface Namespace {
  id: string
  name: string
}

interface Props {
  namespaces: Namespace[]
  activeIds: string[]
  onToggleNamespace: (id: string) => void
  onAddNamespace: (ns: Namespace) => void
  onRemoveNamespace: (id: string) => void
  evalStats?: {
    faithfulness: number
    contextRelevance: number
    answerRelevance: number
    overall: number
    papersCount: number
    jobsRun: number
  }
}

const PROVIDERS = ['openai', 'pinecone', 'tavily'] as const
type Provider = typeof PROVIDERS[number]

export default function Sidebar({
  namespaces,
  activeIds,
  onToggleNamespace,
  onAddNamespace,
  onRemoveNamespace,
  evalStats,
}: Props) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [panel, setPanel] = useState<'profile' | 'keys' | null>(null)
  const [showNsInput, setShowNsInput] = useState(false)
  const [nsId, setNsId] = useState('')
  const [nsName, setNsName] = useState('')

  // Keys panel state
  const [keys, setKeys] = useState<Record<Provider, string>>({
    openai: '', pinecone: '', tavily: '',
  })
  const [showKey, setShowKey] = useState<Record<Provider, boolean>>({
    openai: false, pinecone: false, tavily: false,
  })
  const [savedProviders, setSavedProviders] = useState<Set<string>>(new Set())
  const [keyLoading, setKeyLoading] = useState(false)
  const [keyError, setKeyError] = useState('')
  const [keySuccess, setKeySuccess] = useState('')

  const togglePanel = (p: 'profile' | 'keys') =>
    setPanel(prev => prev === p ? null : p)

  const handleAddNamespace = () => {
    if (!nsId.trim()) return
    onAddNamespace({
      id: nsId.trim(),
      name: nsName.trim() || nsId.trim(),
    })
    setNsId('')
    setNsName('')
    setShowNsInput(false)
  }

  const handleSaveKeys = async () => {
    setKeyLoading(true)
    setKeyError('')
    setKeySuccess('')
    try {
      const toSave = PROVIDERS.filter(p => keys[p].trim())
      await Promise.all(
        toSave.map(p => authApi.addKey(p, keys[p].trim()))
      )
      setSavedProviders(new Set(toSave))
      setKeySuccess(`${toSave.length} key(s) saved successfully.`)
      setKeys({ openai: '', pinecone: '', tavily: '' })
    } catch (err: any) {
      setKeyError(err?.response?.data?.detail || 'Failed to save keys.')
    } finally {
      setKeyLoading(false)
    }
  }

  // Chart data from evalStats
  const chartRows = evalStats ? [
    { label: 'Faith', val: Math.round(evalStats.faithfulness * 100) },
    { label: 'Ctx', val: Math.round(evalStats.contextRelevance * 100) },
    { label: 'Ans', val: Math.round(evalStats.answerRelevance * 100) },
    { label: 'Avg', val: Math.round(evalStats.overall * 100), warm: true },
  ] : [
    { label: 'Faith', val: 82 },
    { label: 'Ctx', val: 73 },
    { label: 'Ans', val: 64 },
    { label: 'Avg', val: 73, warm: true },
  ]

  const initials = user?.email?.[0]?.toUpperCase() ?? 'U'

  return (
    <>
      <style>{sidebarCss}</style>
      <div className="sidebar">

        {/* ── Charts section ── */}
        <div className="sb-section charts-section">
          <div className="sb-label">Eval Metrics</div>
          <div className="chart-area">
            {chartRows.map(row => (
              <div className="chart-row" key={row.label}>
                <span className="chart-row-label">{row.label}</span>
                <div className="chart-track">
                  <div
                    className={`chart-fill${(row as any).warm ? ' warm' : ''}`}
                    style={{ width: `${row.val}%` }}
                  />
                </div>
                <span className="chart-row-val">{row.val}%</span>
              </div>
            ))}
            <div className="stat-row">
              <div className="stat-card">
                <div className="stat-val">
                  {evalStats?.papersCount ?? namespaces.length}
                </div>
                <div className="stat-lbl">papers</div>
              </div>
              <div className="stat-card">
                <div className="stat-val">
                  {evalStats ? `${Math.round(evalStats.overall * 100)}%` : '—'}
                </div>
                <div className="stat-lbl">avg score</div>
              </div>
              <div className="stat-card">
                <div className="stat-val">{evalStats?.jobsRun ?? 0}</div>
                <div className="stat-lbl">jobs run</div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Namespaces section ── */}
        <div className="sb-section ns-section">
          <div className="sb-label">
            Namespaces · Paper IDs
            <span className="ns-count">{namespaces.length}</span>
          </div>
          <div className="ns-list">
            {namespaces.map(ns => (
              <div
                key={ns.id}
                className={`ns-item${activeIds.includes(ns.id) ? ' active' : ''}`}
                onClick={() => onToggleNamespace(ns.id)}
              >
                <div className="ns-dot" />
                <div className="ns-info">
                  <div className="ns-name">{ns.name}</div>
                  <div className="ns-id">{ns.id.slice(0, 12)}...</div>
                </div>
                <span
                  className="ns-remove"
                  onClick={e => { e.stopPropagation(); onRemoveNamespace(ns.id) }}
                >✕</span>
              </div>
            ))}

            {showNsInput ? (
              <div className="ns-input-block">
                <input
                  className="ns-input"
                  placeholder="paper ID (hash)"
                  value={nsId}
                  onChange={e => setNsId(e.target.value)}
                  autoFocus
                />
                <input
                  className="ns-input"
                  placeholder="friendly name (optional)"
                  value={nsName}
                  onChange={e => setNsName(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAddNamespace()}
                />
                <div className="ns-input-actions">
                  <button className="ns-btn-add" onClick={handleAddNamespace}>
                    Add
                  </button>
                  <button
                    className="ns-btn-cancel"
                    onClick={() => { setShowNsInput(false); setNsId(''); setNsName('') }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="ns-add-btn" onClick={() => setShowNsInput(true)}>
                + add namespace
              </div>
            )}
          </div>
        </div>

        {/* ── Icons bar ── */}
        <div className="icons-bar">
          <div
            className={`icon-btn${panel === 'profile' ? ' active' : ''}`}
            title="Profile"
            onClick={() => togglePanel('profile')}
          >👤</div>
          <div
            className={`icon-btn key-icon${panel === 'keys' ? ' active' : ''}`}
            title="API Keys"
            onClick={() => togglePanel('keys')}
          >🔑</div>
          <div
            className="icon-btn"
            title="Settings"
            onClick={() => navigate('/settings')}
          >⚙️</div>
        </div>

        {/* ── Profile panel ── */}
        <div className={`slide-panel${panel === 'profile' ? ' open' : ''}`}>
          <div className="panel-header">
            <span className="panel-title">Profile</span>
            <button className="panel-close" onClick={() => setPanel(null)}>✕</button>
          </div>
          <div className="panel-body">
            <div className="profile-avatar">{initials}</div>
            <div className="profile-name">
              {user?.email?.split('@')[0] ?? 'User'}
            </div>
            <div className="profile-email">{user?.email}</div>
            <div className="profile-stats">
              <div className="p-stat">
                <div className="p-stat-val">{namespaces.length}</div>
                <div className="p-stat-lbl">papers</div>
              </div>
              <div className="p-stat">
                <div className="p-stat-val">{evalStats?.jobsRun ?? 0}</div>
                <div className="p-stat-lbl">jobs</div>
              </div>
              <div className="p-stat">
                <div className="p-stat-val">
                  {evalStats ? `${Math.round(evalStats.overall * 100)}%` : '—'}
                </div>
                <div className="p-stat-lbl">avg score</div>
              </div>
            </div>
            <button className="logout-btn" onClick={logout}>Sign out</button>
          </div>
        </div>

        {/* ── API Keys panel ── */}
        <div className={`slide-panel${panel === 'keys' ? ' open' : ''}`}>
          <div className="panel-header">
            <span className="panel-title">API Keys</span>
            <button className="panel-close" onClick={() => setPanel(null)}>✕</button>
          </div>
          <div className="panel-body">
            <p className="keys-hint">
              Keys are Fernet-encrypted before storage.
              Only the last 4 characters are saved as a hint.
            </p>
            {PROVIDERS.map(provider => (
              <div className="key-field" key={provider}>
                <div className="key-label-row">
                  <span className="key-label">{provider}</span>
                  {savedProviders.has(provider) && (
                    <span className="key-badge saved">saved</span>
                  )}
                </div>
                <div className="key-input-wrap">
                  <input
                    className="key-input"
                    type={showKey[provider] ? 'text' : 'password'}
                    placeholder={`${provider}-key-...`}
                    value={keys[provider]}
                    onChange={e => setKeys(k => ({ ...k, [provider]: e.target.value }))}
                  />
                  <span
                    className="key-eye"
                    onClick={() => setShowKey(s => ({ ...s, [provider]: !s[provider] }))}
                  >
                    {showKey[provider] ? '🙈' : '👁'}
                  </span>
                </div>
              </div>
            ))}

            {keyError && <div className="key-error">{keyError}</div>}
            {keySuccess && <div className="key-success">{keySuccess}</div>}

            <button
              className="key-save-btn"
              onClick={handleSaveKeys}
              disabled={keyLoading}
              style={{ opacity: keyLoading ? 0.7 : 1 }}
            >
              {keyLoading ? 'Saving...' : 'Save Keys'}
            </button>
          </div>
        </div>

      </div>
    </>
  )
}

const sidebarCss = `
  .sidebar {
    width: 300px;
    min-width: 300px;
    background: var(--sidebar-bg);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    position: relative;
    overflow: hidden;
    z-index: 10;
  }
  .sb-section {
    border-bottom: 1px solid var(--border);
    padding: 18px;
    overflow: hidden;
  }
  .sb-label {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .ns-count {
    background: var(--tag-bg);
    border-radius: 10px;
    padding: 1px 7px;
    font-size: 10px;
    color: var(--text-secondary);
  }
  .charts-section { height: 46%; display: flex; flex-direction: column; }
  .chart-area { flex: 1; display: flex; flex-direction: column; gap: 8px; justify-content: center; }
  .chart-row { display: flex; align-items: center; gap: 8px; }
  .chart-row-label {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    color: var(--text-muted);
    width: 32px;
    text-align: right;
    flex-shrink: 0;
  }
  .chart-track {
    flex: 1;
    height: 5px;
    background: var(--border);
    border-radius: 3px;
    overflow: hidden;
  }
  .chart-fill {
    height: 100%;
    border-radius: 3px;
    background: var(--accent);
    transition: width 0.7s cubic-bezier(0.16,1,0.3,1);
  }
  .chart-fill.warm { background: var(--accent-warm); }
  .chart-row-val {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    color: var(--text-muted);
    width: 28px;
  }
  .stat-row { display: flex; gap: 8px; margin-top: 10px; }
  .stat-card {
    flex: 1;
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 7px;
    padding: 9px 10px;
  }
  .stat-val {
    font-family: 'DM Serif Display', serif;
    font-size: 20px;
    color: var(--text-primary);
    line-height: 1;
  }
  .stat-lbl {
    font-family: 'DM Mono', monospace;
    font-size: 9px;
    color: var(--text-muted);
    margin-top: 2px;
  }
  .ns-section { height: 46%; display: flex; flex-direction: column; }
  .ns-list {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .ns-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 7px;
    cursor: pointer;
    transition: all 0.15s ease;
    user-select: none;
  }
  .ns-item:hover { border-color: var(--accent); background: #fff; }
  .ns-item.active { border-color: var(--accent-warm); background: #fff8f5; }
  .ns-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--text-muted);
    flex-shrink: 0;
    transition: background 0.15s;
  }
  .ns-item.active .ns-dot { background: var(--accent-warm); }
  .ns-info { flex: 1; overflow: hidden; }
  .ns-name {
    font-size: 11px;
    font-weight: 500;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ns-id {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ns-remove {
    font-size: 11px;
    color: var(--text-muted);
    opacity: 0;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 3px;
    transition: opacity 0.15s;
  }
  .ns-item:hover .ns-remove { opacity: 1; }
  .ns-input-block {
    display: flex;
    flex-direction: column;
    gap: 5px;
    padding: 8px;
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 7px;
  }
  .ns-input {
    padding: 6px 9px;
    border: 1px solid var(--border);
    border-radius: 5px;
    background: var(--bg);
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: var(--text-primary);
    outline: none;
    transition: border-color 0.15s;
  }
  .ns-input:focus { border-color: var(--accent); }
  .ns-input-actions { display: flex; gap: 5px; }
  .ns-btn-add {
    flex: 1; padding: 5px;
    background: var(--accent); color: #fff;
    border: none; border-radius: 5px;
    font-family: 'DM Sans', sans-serif;
    font-size: 11px; cursor: pointer;
    transition: opacity 0.15s;
  }
  .ns-btn-add:hover { opacity: 0.85; }
  .ns-btn-cancel {
    flex: 1; padding: 5px;
    background: transparent; color: var(--text-muted);
    border: 1px solid var(--border); border-radius: 5px;
    font-family: 'DM Sans', sans-serif;
    font-size: 11px; cursor: pointer;
  }
  .ns-add-btn {
    display: flex; align-items: center;
    padding: 7px 10px;
    border: 1px dashed var(--border);
    border-radius: 7px;
    cursor: pointer;
    color: var(--text-muted);
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    transition: all 0.15s;
  }
  .ns-add-btn:hover { border-color: var(--accent); color: var(--accent); }
  .icons-bar {
    height: 8%;
    display: flex;
    align-items: center;
    padding: 0 18px;
    gap: 8px;
  }
  .icon-btn {
    width: 34px; height: 34px;
    border-radius: 7px;
    border: 1px solid var(--border);
    background: var(--panel-bg);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    font-size: 15px;
    transition: all 0.15s;
  }
  .icon-btn:hover { border-color: var(--accent); background: #fff; }
  .icon-btn.active { border-color: var(--accent); background: #fff; }
  .key-icon { color: var(--accent); }
  .slide-panel {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    background: var(--panel-bg);
    border-right: 1px solid var(--border);
    z-index: 20;
    transform: translateX(-100%);
    transition: transform 0.28s cubic-bezier(0.16,1,0.3,1);
    display: flex; flex-direction: column;
    overflow: hidden;
  }
  .slide-panel.open { transform: translateX(0); }
  .panel-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 18px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .panel-title {
    font-family: 'DM Serif Display', serif;
    font-size: 16px; color: var(--text-primary);
  }
  .panel-close {
    width: 26px; height: 26px;
    border-radius: 5px;
    border: 1px solid var(--border);
    background: transparent;
    cursor: pointer; font-size: 12px;
    color: var(--text-secondary);
    display: flex; align-items: center; justify-content: center;
    transition: all 0.15s;
  }
  .panel-close:hover { background: var(--border); }
  .panel-body {
    flex: 1; padding: 18px;
    overflow-y: auto;
  }
  .profile-avatar {
    width: 52px; height: 52px;
    border-radius: 50%;
    background: var(--accent);
    color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-family: 'DM Serif Display', serif;
    font-size: 20px;
    margin-bottom: 12px;
  }
  .profile-name {
    font-family: 'DM Serif Display', serif;
    font-size: 17px; color: var(--text-primary);
  }
  .profile-email {
    font-family: 'DM Mono', monospace;
    font-size: 10px; color: var(--text-muted);
    margin-top: 2px; margin-bottom: 16px;
  }
  .profile-stats {
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    gap: 7px; margin-bottom: 16px;
  }
  .p-stat {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 7px; padding: 10px;
  }
  .p-stat-val {
    font-family: 'DM Serif Display', serif;
    font-size: 20px; color: var(--text-primary);
  }
  .p-stat-lbl {
    font-family: 'DM Mono', monospace;
    font-size: 9px; color: var(--text-muted);
    margin-top: 2px;
  }
  .logout-btn {
    width: 100%; padding: 10px;
    border: 1px solid var(--border);
    border-radius: 7px;
    background: transparent;
    font-family: 'DM Sans', sans-serif;
    font-size: 12px; color: var(--text-secondary);
    cursor: pointer; transition: all 0.15s;
  }
  .logout-btn:hover { color: var(--accent-warm); border-color: var(--accent-warm); }
  .keys-hint {
    font-family: 'DM Mono', monospace;
    font-size: 10px; color: var(--text-muted);
    line-height: 1.6; margin-bottom: 16px;
    padding: 10px; background: var(--bg);
    border-radius: 6px; border: 1px solid var(--border);
  }
  .key-field { margin-bottom: 14px; }
  .key-label-row {
    display: flex; align-items: center;
    justify-content: space-between;
    margin-bottom: 5px;
  }
  .key-label {
    font-family: 'DM Mono', monospace;
    font-size: 10px; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--text-muted);
  }
  .key-badge {
    font-family: 'DM Mono', monospace;
    font-size: 9px; padding: 2px 6px;
    border-radius: 10px;
  }
  .key-badge.saved { background: #e8f5e9; color: #2e7d32; }
  .key-badge.missing { background: #fce4ec; color: #c62828; }
  .key-input-wrap { position: relative; }
  .key-input {
    width: 100%; padding: 8px 34px 8px 10px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg);
    font-family: 'DM Mono', monospace;
    font-size: 11px; color: var(--text-primary);
    outline: none; transition: border-color 0.15s;
  }
  .key-input:focus { border-color: var(--accent); }
  .key-eye {
    position: absolute; right: 8px; top: 50%;
    transform: translateY(-50%);
    cursor: pointer; font-size: 12px;
    color: var(--text-muted); user-select: none;
  }
  .key-error {
    padding: 8px 10px; margin-bottom: 10px;
    background: #fce4ec; border: 1px solid #f48fb1;
    border-radius: 6px; font-family: 'DM Mono', monospace;
    font-size: 10px; color: #c62828;
  }
  .key-success {
    padding: 8px 10px; margin-bottom: 10px;
    background: #e8f5e9; border: 1px solid #a5d6a7;
    border-radius: 6px; font-family: 'DM Mono', monospace;
    font-size: 10px; color: #2e7d32;
  }
  .key-save-btn {
    width: 100%; padding: 10px;
    background: var(--accent); color: #fff;
    border: none; border-radius: 7px;
    font-family: 'DM Sans', sans-serif;
    font-size: 13px; font-weight: 500;
    cursor: pointer; transition: opacity 0.15s;
  }
  .key-save-btn:hover { opacity: 0.85; }
`