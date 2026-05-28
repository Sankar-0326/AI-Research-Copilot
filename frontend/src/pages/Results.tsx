import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { analysisApi, type FullReportResponse } from '@/lib/api'

type TabId = 'report' | 'summaries' | 'insights' | 'gaps'

const POLL_INTERVAL = 3000   // 3s between polls
const MAX_POLLS = 100        // give up after ~5 mins

export default function Results() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()

  const [status, setStatus] = useState<'polling' | 'complete' | 'failed'>('polling')
  const [report, setReport] = useState<FullReportResponse | null>(null)
  const [error, setError] = useState('')
  const [pollCount, setPollCount] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const [activeTab, setActiveTab] = useState<TabId>('report')
  const [expandedSummary, setExpandedSummary] = useState<string | null>(null)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const countRef = useRef(0)

  // ── Elapsed timer ────────────────────────────────────────────────────
  useEffect(() => {
    timerRef.current = setInterval(() => {
      setElapsed(s => s + 1)
    }, 1000)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  // ── Polling ──────────────────────────────────────────────────────────
  const poll = useCallback(async () => {
    if (!jobId) return
    countRef.current += 1
    setPollCount(countRef.current)

    if (countRef.current > MAX_POLLS) {
      if (pollRef.current) clearInterval(pollRef.current)
      setStatus('failed')
      setError('Analysis timed out after 5 minutes. Please try again.')
      return
    }

    try {
      const { data } = await analysisApi.getReport(jobId)
      if (pollRef.current) clearInterval(pollRef.current)
      if (timerRef.current) clearInterval(timerRef.current)
      setReport(data)
      setStatus('complete')
    } catch (err: any) {
      const status = err?.response?.status
      const detail = err?.response?.data?.detail ?? ''

      if (status === 202) {
        // Still running — continue polling
        return
      }
      if (status === 500) {
        if (pollRef.current) clearInterval(pollRef.current)
        if (timerRef.current) clearInterval(timerRef.current)
        setStatus('failed')
        setError(detail || 'Pipeline failed.')
      }
    }
  }, [jobId])

  useEffect(() => {
    poll() // immediate first poll
    pollRef.current = setInterval(poll, POLL_INTERVAL)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [poll])

  // ── Helpers ──────────────────────────────────────────────────────────
  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

  const copyReport = () => {
    if (report?.final_report) {
      navigator.clipboard.writeText(report.final_report)
    }
  }

  // ── Polling UI ───────────────────────────────────────────────────────
  if (status === 'polling') {
    return (
      <>
        <style>{resultsCss}</style>
        <div className="results-root">
          <div className="polling-card">
            <div className="polling-spinner-wrap">
              <div className="polling-ring" />
              <div className="polling-ring ring-2" />
            </div>
            <h2 className="polling-title">Analyzing papers</h2>
            <p className="polling-sub">
              Multi-agent pipeline running — summarization → insights → gap detection
            </p>
            <div className="polling-meta">
              <div className="polling-chip">
                <span className="polling-chip-label">elapsed</span>
                <span className="polling-chip-val">{fmt(elapsed)}</span>
              </div>
              <div className="polling-chip">
                <span className="polling-chip-label">polls</span>
                <span className="polling-chip-val">{pollCount}</span>
              </div>
              <div className="polling-chip">
                <span className="polling-chip-label">job</span>
                <span className="polling-chip-val">{jobId?.slice(0, 8)}...</span>
              </div>
            </div>
            <div className="agent-pipeline">
              {['planner', 'summarization', 'insight', 'gap_detection', 'report'].map((a, i) => (
                <div key={a} className="agent-step">
                  <div className="agent-dot animating" style={{
                    animationDelay: `${i * 0.3}s`
                  }} />
                  <span className="agent-label">{a}</span>
                  {i < 4 && <div className="agent-line" />}
                </div>
              ))}
            </div>
            <button
              className="back-btn"
              onClick={() => navigate('/')}
            >
              ← Back to dashboard
            </button>
          </div>
        </div>
      </>
    )
  }

  // ── Failed UI ────────────────────────────────────────────────────────
  if (status === 'failed') {
    return (
      <>
        <style>{resultsCss}</style>
        <div className="results-root">
          <div className="polling-card">
            <div className="fail-icon">✕</div>
            <h2 className="polling-title">Analysis failed</h2>
            <p className="polling-sub">{error}</p>
            <button
              className="analyze-btn"
              onClick={() => navigate('/')}
              style={{ marginTop: 24 }}
            >
              ← Back to dashboard
            </button>
          </div>
        </div>
      </>
    )
  }

  // ── Results UI ───────────────────────────────────────────────────────
  const summaryEntries = Object.entries(report?.summaries ?? {})
  const insights = report?.insights ?? []
  const gaps = report?.research_gaps ?? []
  const agents = report?.completed_agents ?? []
  const errors = report?.errors ?? []

  return (
    <>
      <style>{resultsCss}</style>
      <div className="results-layout">

        {/* ── Topbar ── */}
        <div className="results-topbar">
          <div className="results-topbar-left">
            <button className="back-link" onClick={() => navigate('/')}>
              ← Dashboard
            </button>
            <div className="results-title">
              Analysis Report
              <span className="results-title-sub">
                / {jobId?.slice(0, 8)}...
              </span>
            </div>
          </div>
          <div className="results-topbar-right">
            <div className="meta-chip">
              ⏱ {fmt(elapsed)}
            </div>
            <div className="meta-chip">
              📄 {report?.paper_ids.length} paper{(report?.paper_ids.length ?? 0) > 1 ? 's' : ''}
            </div>
            {agents.map(a => (
              <div key={a} className="agent-chip">{a}</div>
            ))}
            {errors.length > 0 && (
              <div className="warn-chip">⚠ {errors.length} warning{errors.length > 1 ? 's' : ''}</div>
            )}
            <button className="copy-btn" onClick={copyReport}>
              Copy report
            </button>
          </div>
        </div>

        {/* ── Query bar ── */}
        <div className="query-bar">
          <span className="query-bar-label">query</span>
          <span className="query-bar-text">{report?.query}</span>
        </div>

        {/* ── Tabs ── */}
        <div className="tabs-bar">
          {([
            { id: 'report',    label: 'Full Report',   count: null },
            { id: 'summaries', label: 'Summaries',     count: summaryEntries.length },
            { id: 'insights',  label: 'Insights',      count: insights.length },
            { id: 'gaps',      label: 'Gaps & Future', count: gaps.length },
          ] as { id: TabId; label: string; count: number | null }[]).map(tab => (
            <button
              key={tab.id}
              className={`tab-btn${activeTab === tab.id ? ' active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
              {tab.count !== null && (
                <span className="tab-count">{tab.count}</span>
              )}
            </button>
          ))}
        </div>

        {/* ── Tab content ── */}
        <div className="results-body">

          {/* Full report tab */}
          {activeTab === 'report' && (
            <div className="report-prose">
              {report?.final_report.split('\n').map((line, i) => {
                if (line.startsWith('# ')) return (
                  <h1 key={i} className="prose-h1">{line.slice(2)}</h1>
                )
                if (line.startsWith('## ')) return (
                  <h2 key={i} className="prose-h2">{line.slice(3)}</h2>
                )
                if (line.startsWith('### ')) return (
                  <h3 key={i} className="prose-h3">{line.slice(4)}</h3>
                )
                if (line.startsWith('- ')) return (
                  <div key={i} className="prose-bullet">
                    <span className="prose-bullet-dot" />
                    <span>{line.slice(2)}</span>
                  </div>
                )
                if (line.startsWith('---')) return (
                  <hr key={i} className="prose-hr" />
                )
                if (line.startsWith('**') && line.endsWith('**')) return (
                  <p key={i} className="prose-bold">{line.slice(2, -2)}</p>
                )
                if (!line.trim()) return <div key={i} className="prose-spacer" />
                return <p key={i} className="prose-p">{line}</p>
              })}
            </div>
          )}

          {/* Summaries tab */}
          {activeTab === 'summaries' && (
            <div className="summaries-list">
              {summaryEntries.length === 0 && (
                <div className="empty-state">No summaries generated.</div>
              )}
              {summaryEntries.map(([paperId, summary]) => (
                <div key={paperId} className="summary-card">
                  <div
                    className="summary-card-header"
                    onClick={() => setExpandedSummary(
                      expandedSummary === paperId ? null : paperId
                    )}
                  >
                    <div className="summary-card-id">
                      <div className="summary-dot" />
                      <span className="summary-paper-id">
                        Paper {paperId.slice(0, 8)}...
                      </span>
                    </div>
                    <span className="summary-toggle">
                      {expandedSummary === paperId ? '▲' : '▼'}
                    </span>
                  </div>
                  {expandedSummary === paperId && (
                    <div className="summary-body">
                      {summary.split('\n').map((line, i) => {
                        if (line.startsWith('## ')) return (
                          <h3 key={i} className="prose-h3"
                            style={{ marginTop: 16 }}>
                            {line.slice(3)}
                          </h3>
                        )
                        if (line.startsWith('- ')) return (
                          <div key={i} className="prose-bullet">
                            <span className="prose-bullet-dot" />
                            <span>{line.slice(2)}</span>
                          </div>
                        )
                        if (!line.trim()) return (
                          <div key={i} className="prose-spacer" />
                        )
                        return <p key={i} className="prose-p">{line}</p>
                      })}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Insights tab */}
          {activeTab === 'insights' && (
            <div className="insight-list">
              {insights.length === 0 && (
                <div className="empty-state">No insights generated.</div>
              )}
              {insights.map((block, i) => (
                <div key={i} className="insight-card">
                  {block.split('\n').map((line, j) => {
                    if (line.startsWith('## ')) return (
                      <h2 key={j} className="prose-h2">{line.slice(3)}</h2>
                    )
                    if (line.startsWith('- ')) return (
                      <div key={j} className="prose-bullet">
                        <span className="prose-bullet-dot" />
                        <span>{line.slice(2)}</span>
                      </div>
                    )
                    if (!line.trim()) return (
                      <div key={j} className="prose-spacer" />
                    )
                    return <p key={j} className="prose-p">{line}</p>
                  })}
                </div>
              ))}
            </div>
          )}

          {/* Gaps tab */}
          {activeTab === 'gaps' && (
            <div className="gaps-list">
              {gaps.length === 0 && (
                <div className="empty-state">No gaps detected.</div>
              )}
              {gaps.map((block: string, i: number) => (
                <div key={i} className="gap-card">
                  {block.split('\n').map((line: string, j: number) => {
                    if (line.startsWith('## ')) return (
                      <h2 key={j} className="prose-h2">{line.slice(3)}</h2>
                    )
                    if (line.match(/^\d+\./)) return (
                      <div key={j} className="gap-numbered">
                        <span className="gap-number">
                          {line.match(/^(\d+)\./)?.[1]}
                        </span>
                        <span>{line.replace(/^\d+\.\s*/, '')}</span>
                      </div>
                    )
                    if (line.startsWith('- ')) return (
                      <div key={j} className="prose-bullet">
                        <span className="prose-bullet-dot" />
                        <span>{line.slice(2)}</span>
                      </div>
                    )
                    if (!line.trim()) return (
                      <div key={j} className="prose-spacer" />
                    )
                    return <p key={j} className="prose-p">{line}</p>
                  })}
                </div>
              ))}
            </div>
          )}

        </div>
      </div>
    </>
  )
}

const resultsCss = `
  .results-root {
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg);
    font-family: 'DM Sans', sans-serif;
  }
  .polling-card {
    max-width: 480px;
    width: 100%;
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 40px 36px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 14px;
  }
  .polling-spinner-wrap {
    position: relative;
    width: 56px; height: 56px;
    margin-bottom: 8px;
  }
  .polling-ring {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    animation: spin 1s linear infinite;
  }
  .ring-2 {
    inset: 8px;
    border-top-color: var(--accent-warm);
    animation-duration: 0.7s;
    animation-direction: reverse;
  }
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  .polling-title {
    font-family: 'DM Serif Display', serif;
    font-size: 22px;
    color: var(--text-primary);
  }
  .polling-sub {
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.6;
    font-family: 'DM Mono', monospace;
    max-width: 340px;
  }
  .polling-meta {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: center;
  }
  .polling-chip {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 20px;
  }
  .polling-chip-label {
    font-family: 'DM Mono', monospace;
    font-size: 9px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .polling-chip-val {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: var(--text-primary);
    font-weight: 500;
  }
  .agent-pipeline {
    display: flex;
    align-items: center;
    gap: 0;
    margin: 8px 0;
    flex-wrap: wrap;
    justify-content: center;
    gap: 4px;
  }
  .agent-step {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .agent-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--border);
  }
  .agent-dot.animating {
    background: var(--accent-warm);
    animation: pulse 1.4s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 0.3; transform: scale(0.8); }
    50% { opacity: 1; transform: scale(1.2); }
  }
  .agent-label {
    font-family: 'DM Mono', monospace;
    font-size: 9px;
    color: var(--text-muted);
    letter-spacing: 0.04em;
  }
  .agent-line {
    width: 16px; height: 1px;
    background: var(--border);
    margin: 0 2px;
  }
  .fail-icon {
    width: 48px; height: 48px;
    border-radius: 50%;
    background: #fce4ec;
    color: #c62828;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    font-weight: 700;
    margin-bottom: 8px;
  }
  .back-btn {
    padding: 9px 20px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: transparent;
    font-family: 'DM Sans', sans-serif;
    font-size: 12px;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s;
    margin-top: 8px;
  }
  .back-btn:hover { border-color: var(--accent); color: var(--accent); }

  /* ── Results layout ── */
  .results-layout {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
    font-family: 'DM Sans', sans-serif;
    background: var(--bg);
  }
  .results-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 24px;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
    flex-shrink: 0;
    gap: 12px;
    flex-wrap: wrap;
  }
  .results-topbar-left {
    display: flex;
    align-items: center;
    gap: 14px;
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
  .results-title {
    font-family: 'DM Serif Display', serif;
    font-size: 18px;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .results-title-sub {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    color: var(--text-muted);
  }
  .results-topbar-right {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .meta-chip {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    padding: 4px 10px;
    border-radius: 20px;
    border: 1px solid var(--border);
    color: var(--text-muted);
  }
  .agent-chip {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    padding: 3px 8px;
    border-radius: 20px;
    background: #e8f5e9;
    color: #2e7d32;
    border: 1px solid #a5d6a7;
  }
  .warn-chip {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    padding: 3px 8px;
    border-radius: 20px;
    background: #fff8e1;
    color: #f57f17;
    border: 1px solid #ffe082;
  }
  .copy-btn {
    padding: 6px 14px;
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 7px;
    font-family: 'DM Sans', sans-serif;
    font-size: 11px;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .copy-btn:hover { opacity: 0.85; }
  .query-bar {
    padding: 10px 24px;
    background: var(--sidebar-bg);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: flex-start;
    gap: 10px;
    flex-shrink: 0;
  }
  .query-bar-label {
    font-family: 'DM Mono', monospace;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-muted);
    padding-top: 1px;
    flex-shrink: 0;
  }
  .query-bar-text {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.5;
    font-family: 'DM Sans', sans-serif;
  }
  .tabs-bar {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
    padding: 0 24px;
    flex-shrink: 0;
  }
  .tab-btn {
    padding: 12px 18px;
    border: none;
    border-bottom: 2px solid transparent;
    background: transparent;
    font-family: 'DM Sans', sans-serif;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: -1px;
  }
  .tab-btn:hover { color: var(--text-primary); }
  .tab-btn.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }
  .tab-count {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 10px;
    background: var(--tag-bg);
    color: var(--text-secondary);
  }
  .results-body {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
  }

  /* ── Prose rendering ── */
  .report-prose {
    max-width: 760px;
    margin: 0 auto;
  }
  .prose-h1 {
    font-family: 'DM Serif Display', serif;
    font-size: 26px;
    color: var(--text-primary);
    margin-bottom: 6px;
    margin-top: 24px;
  }
  .prose-h2 {
    font-family: 'DM Serif Display', serif;
    font-size: 18px;
    color: var(--text-primary);
    margin-bottom: 4px;
    margin-top: 20px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
  }
  .prose-h3 {
    font-family: 'DM Sans', sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    margin-top: 14px;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-size: 11px;
    color: var(--text-secondary);
  }
  .prose-p {
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.7;
    margin: 3px 0;
  }
  .prose-bold {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 6px 0;
  }
  .prose-bullet {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin: 5px 0;
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.6;
  }
  .prose-bullet-dot {
    width: 5px; height: 5px;
    border-radius: 50%;
    background: var(--accent-warm);
    flex-shrink: 0;
    margin-top: 7px;
  }
  .prose-hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 20px 0;
  }
  .prose-spacer { height: 6px; }

  /* ── Summaries ── */
  .summaries-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
    max-width: 760px;
    margin: 0 auto;
  }
  .summary-card {
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }
  .summary-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    cursor: pointer;
    transition: background 0.15s;
  }
  .summary-card-header:hover { background: #fff; }
  .summary-card-id {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .summary-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--accent-warm);
  }
  .summary-paper-id {
    font-family: 'DM Mono', monospace;
    font-size: 12px;
    color: var(--text-primary);
  }
  .summary-toggle {
    font-size: 10px;
    color: var(--text-muted);
  }
  .summary-body {
    padding: 16px;
    border-top: 1px solid var(--border);
    background: var(--bg);
  }

  /* ── Insights ── */
  .insight-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
    max-width: 760px;
    margin: 0 auto;
  }
  .insight-card {
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
  }

  /* ── Gaps ── */
  .gaps-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
    max-width: 760px;
    margin: 0 auto;
  }
  .gap-card {
    background: var(--panel-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
  }
  .gap-numbered {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    margin: 8px 0;
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.6;
  }
  .gap-number {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    font-weight: 600;
    color: var(--accent-warm);
    background: #fff8f5;
    border: 1px solid #ffd5c5;
    border-radius: 5px;
    padding: 1px 7px;
    flex-shrink: 0;
    margin-top: 2px;
  }
  .empty-state {
    font-family: 'DM Mono', monospace;
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
    padding: 40px;
  }
  .analyze-btn {
    padding: 10px 22px;
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
`