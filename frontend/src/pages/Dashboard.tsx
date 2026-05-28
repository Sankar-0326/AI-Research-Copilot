import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Sidebar from '@/components/Sidebar'
import { papersApi, analysisApi } from '@/lib/api'

interface Namespace {
  id: string
  name: string
}

type RetrievalMode = 'single' | 'cross' | 'hybrid'

const FRIENDLY_NAMES_KEY = 'rc_friendly_names'
const NAMESPACES_KEY = 'rc_namespaces'
const ACTIVE_IDS_KEY = 'rc_active_ids'

function getFriendlyNames(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(FRIENDLY_NAMES_KEY) || '{}')
  } catch { return {} }
}

function saveFriendlyName(paperId: string, name: string) {
  const names = getFriendlyNames()
  names[paperId] = name
  localStorage.setItem(FRIENDLY_NAMES_KEY, JSON.stringify(names))
}

export default function Dashboard() {
  const navigate = useNavigate()

  // ── Namespaces — initialized from localStorage ──────────────────────
  const [namespaces, setNamespaces] = useState<Namespace[]>(() => {
    try {
      const saved = localStorage.getItem(NAMESPACES_KEY)
      return saved ? JSON.parse(saved) : []
    } catch { return [] }
  })

  const [activeIds, setActiveIds] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem(ACTIVE_IDS_KEY)
      return saved ? JSON.parse(saved) : []
    } catch { return [] }
  })

  const [loadingNamespaces, setLoadingNamespaces] = useState(false)

  // Upload state
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [uploadSuccess, setUploadSuccess] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  // Query state
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<RetrievalMode>('hybrid')
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeError, setAnalyzeError] = useState('')

  // ── Persist namespaces to localStorage on every change ──────────────
  useEffect(() => {
    localStorage.setItem(NAMESPACES_KEY, JSON.stringify(namespaces))
  }, [namespaces])

  useEffect(() => {
    localStorage.setItem(ACTIVE_IDS_KEY, JSON.stringify(activeIds))
  }, [activeIds])

  // ── Load namespaces from Pinecone on mount ──────────────────────────
  // Pinecone is the source of truth — merges with localStorage names
  useEffect(() => {
    const loadFromPinecone = async () => {
      setLoadingNamespaces(true)
      try {
        const { data } = await papersApi.list()
        const friendlyNames = getFriendlyNames()

        if (data.namespaces.length > 0) {
          setNamespaces(prev => {
            const existingIds = new Set(prev.map(n => n.id))
            const newFromPinecone = data.namespaces
              .filter(n => !existingIds.has(n.id))
              .map(n => ({
                id: n.id,
                // Use saved friendly name if available, else show truncated ID
                name: friendlyNames[n.id] || `Paper (${n.id.slice(0, 8)}...)`,
              }))
            return [...prev, ...newFromPinecone]
          })
        }
      } catch (err) {
        // Non-fatal — user can still upload and add namespaces manually
        console.warn('Could not load namespaces from Pinecone:', err)
      } finally {
        setLoadingNamespaces(false)
      }
    }

    loadFromPinecone()
  }, []) // runs once on mount

  // ── Namespace handlers ──────────────────────────────────────────────

  const handleToggleNamespace = (id: string) => {
    setActiveIds(prev =>
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    )
  }

  const handleAddNamespace = (ns: Namespace) => {
    setNamespaces(prev => {
      if (prev.find(n => n.id === ns.id)) return prev
      return [...prev, ns]
    })
    setActiveIds(prev =>
      prev.includes(ns.id) ? prev : [...prev, ns.id]
    )
  }

  const handleRemoveNamespace = (id: string) => {
    setNamespaces(prev => prev.filter(n => n.id !== id))
    setActiveIds(prev => prev.filter(i => i !== id))
  }

  // ── Upload ──────────────────────────────────────────────────────────

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploading(true)
    setUploadError('')
    setUploadSuccess('')

    const results: string[] = []
    const errors: string[] = []

    for (const file of Array.from(files)) {
      if (file.type !== 'application/pdf') {
        errors.push(`${file.name}: not a PDF`)
        continue
      }
      try {
        const { data } = await papersApi.upload(file)
        const friendlyName = file.name.replace('.pdf', '')

        // Save friendly name to localStorage for future loads
        saveFriendlyName(data.paper_id, friendlyName)

        // Add to sidebar immediately
        handleAddNamespace({ id: data.paper_id, name: friendlyName })
        results.push(`${file.name} → ${data.chunks_stored} chunks`)

      } catch (err: any) {
        const detail = err?.response?.data?.detail || 'upload failed'
        errors.push(`${file.name}: ${detail}`)
      }
    }

    if (results.length > 0) setUploadSuccess(results.join(' · '))
    if (errors.length > 0) setUploadError(errors.join(' · '))
    setUploading(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    handleFiles(e.dataTransfer.files)
  }

  // ── Analyze ─────────────────────────────────────────────────────────

  const handleAnalyze = async () => {
    if (!query.trim()) {
      setAnalyzeError('Please enter a research query.')
      return
    }
    if (activeIds.length === 0) {
      setAnalyzeError('Select at least one namespace (paper ID) to analyze.')
      return
    }

    setAnalyzing(true)
    setAnalyzeError('')

    try {
      const { data } = await analysisApi.analyze({
        query: query.trim(),
        paper_ids: activeIds,
        retrieval_mode: mode,
      })
      navigate(`/results/${data.job_id}`)
    } catch (err: any) {
      setAnalyzeError(
        err?.response?.data?.detail || 'Failed to start analysis.'
      )
      setAnalyzing(false)
    }
  }

  return (
    <>
      <style>{dashCss}</style>
      <div className="dash-layout">

        <Sidebar
          namespaces={namespaces}
          activeIds={activeIds}
          onToggleNamespace={handleToggleNamespace}
          onAddNamespace={handleAddNamespace}
          onRemoveNamespace={handleRemoveNamespace}
        />

        {/* ── Main content ── */}
        <div className="dash-main">

          {/* Topbar */}
          <div className="dash-topbar">
            <div className="dash-title">
              Research Copilot
              <span className="dash-title-sub">/ dashboard</span>
            </div>
            <div className="topbar-right">
              {loadingNamespaces && (
                <div className="status-chip">
                  <div className="loading-dot" />
                  syncing papers...
                </div>
              )}
              {activeIds.length > 0 && (
                <div className="active-chip">
                  {activeIds.length} paper{activeIds.length > 1 ? 's' : ''} selected
                </div>
              )}
              <div className="status-chip">
                <div className="status-dot" />
                connected
              </div>
            </div>
          </div>

          {/* Body */}
          <div className="dash-body">

            {/* Upload zone */}
            <div
              className={`upload-zone${dragOver ? ' drag-over' : ''}${uploading ? ' uploading' : ''}`}
              onDragOver={e => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => !uploading && fileRef.current?.click()}
            >
              <input
                ref={fileRef}
                type="file"
                accept=".pdf"
                multiple
                style={{ display: 'none' }}
                onChange={e => handleFiles(e.target.files)}
              />
              {uploading ? (
                <>
                  <div className="upload-spinner" />
                  <div className="upload-title">Processing papers...</div>
                  <div className="upload-sub">extracting · chunking · embedding</div>
                </>
              ) : (
                <>
                  <div className="upload-icon">⬆</div>
                  <div className="upload-title">
                    {dragOver ? 'Drop to upload' : 'Drop research papers here'}
                  </div>
                  <div className="upload-sub">
                    PDF only · max 50MB per file · multiple files supported
                  </div>
                </>
              )}
            </div>

            {/* Upload feedback */}
            {uploadSuccess && (
              <div className="feedback-success">✓ {uploadSuccess}</div>
            )}
            {uploadError && (
              <div className="feedback-error">⚠ {uploadError}</div>
            )}

            {/* Query card */}
            <div className="query-card">
              <div className="query-label">Research Query</div>
              <textarea
                className="query-textarea"
                placeholder="What are the key contributions, methodologies, and research gaps across these papers?"
                value={query}
                onChange={e => setQuery(e.target.value)}
                rows={3}
              />
              <div className="query-footer">
                <div className="mode-tabs">
                  {(['single', 'cross', 'hybrid'] as RetrievalMode[]).map(m => (
                    <button
                      key={m}
                      className={`mode-tab${mode === m ? ' active' : ''}`}
                      onClick={() => setMode(m)}
                    >
                      {m}
                    </button>
                  ))}
                </div>
                <button
                  className="analyze-btn"
                  onClick={handleAnalyze}
                  disabled={analyzing}
                  style={{ opacity: analyzing ? 0.7 : 1 }}
                >
                  {analyzing ? 'Starting...' : 'Analyze →'}
                </button>
              </div>
              {analyzeError && (
                <div className="feedback-error" style={{ marginTop: 10 }}>
                  ⚠ {analyzeError}
                </div>
              )}
            </div>

            {/* Info cards */}
            <div className="info-grid">
              {[
                {
                  icon: '📄',
                  title: 'Summaries',
                  body: 'Structured per-paper summaries — problem, contributions, methodology, findings, limitations.',
                },
                {
                  icon: '🔗',
                  title: 'Cross-Paper Insights',
                  body: 'Non-obvious connections, contradictions, and convergent themes across the full corpus.',
                },
                {
                  icon: '🔍',
                  title: 'Research Gaps',
                  body: 'Unanswered questions, underexplored domains, and methodological weaknesses.',
                },
                {
                  icon: '🚀',
                  title: 'Future Directions',
                  body: 'Concrete, actionable research directions suggested by the gap detection agent.',
                },
              ].map(card => (
                <div key={card.title} className="info-card">
                  <div className="info-card-title">
                    {card.icon} {card.title}
                  </div>
                  <div className="info-card-body">{card.body}</div>
                </div>
              ))}
            </div>

          </div>
        </div>
      </div>
    </>
  )
}

const dashCss = `
  .dash-layout {
    display: flex;
    height: 100vh;
    overflow: hidden;
    font-family: 'DM Sans', sans-serif;
  }
  .dash-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-width: 0;
  }
  .dash-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
    flex-shrink: 0;
  }
  .dash-title {
    font-family: 'DM Serif Display', serif;
    font-size: 20px;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .dash-title-sub {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    color: var(--text-muted);
    letter-spacing: 0.06em;
  }
  .topbar-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .active-chip {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    padding: 4px 10px;
    border-radius: 20px;
    background: #fff8f5;
    border: 1px solid var(--accent-warm);
    color: var(--accent-warm);
  }
  .status-chip {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    padding: 4px 10px;
    border-radius: 20px;
    border: 1px solid var(--border);
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .status-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: #4caf50;
  }
  .loading-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--accent-warm);
    animation: pulse 1.2s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 0.3; }
    50% { opacity: 1; }
  }
  .dash-body {
    flex: 1;
    padding: 24px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .upload-zone {
    border: 1.5px dashed var(--border);
    border-radius: 12px;
    padding: 32px 24px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    background: var(--panel-bg);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }
  .upload-zone:hover { border-color: var(--accent); background: #fff; }
  .upload-zone.drag-over {
    border-color: var(--accent-warm);
    background: #fff8f5;
    transform: scale(1.01);
  }
  .upload-zone.uploading { opacity: 0.7; cursor: not-allowed; }
  .upload-icon { font-size: 26px; }
  .upload-title {
    font-family: 'DM Serif Display', serif;
    font-size: 16px;
    color: var(--text-primary);
  }
  .upload-sub {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: var(--text-muted);
  }
  .upload-spinner {
    width: 28px; height: 28px;
    border: 2px solid var(--border);
    border-top: 2px solid var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  .feedback-success {
    padding: 9px 14px;
    background: #e8f5e9;
    border: 1px solid #a5d6a7;
    border-radius: 7px;
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: #2e7d32;
  }
  .feedback-error {
    padding: 9px 14px;
    background: #fce4ec;
    border: 1px solid #f48fb1;
    border-radius: 7px;
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: #c62828;
  }
  .query-card {
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px;
  }
  .query-label {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 10px;
  }
  .query-textarea {
    width: 100%;
    padding: 11px 13px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg);
    font-family: 'DM Sans', sans-serif;
    font-size: 13px;
    color: var(--text-primary);
    resize: vertical;
    outline: none;
    transition: border-color 0.15s;
    line-height: 1.5;
  }
  .query-textarea:focus { border-color: var(--accent); }
  .query-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 12px;
  }
  .mode-tabs {
    display: flex;
    gap: 3px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 7px;
    padding: 3px;
  }
  .mode-tab {
    padding: 5px 12px;
    border-radius: 5px;
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    cursor: pointer;
    color: var(--text-muted);
    transition: all 0.15s;
    border: none;
    background: transparent;
  }
  .mode-tab.active { background: var(--accent); color: #fff; }
  .analyze-btn {
    padding: 9px 22px;
    background: var(--accent-warm);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-family: 'DM Sans', sans-serif;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .analyze-btn:hover { opacity: 0.88; }
  .info-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  .info-card {
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
  }
  .info-card-title {
    font-family: 'DM Serif Display', serif;
    font-size: 14px;
    color: var(--text-primary);
    margin-bottom: 8px;
  }
  .info-card-body {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.6;
  }
`