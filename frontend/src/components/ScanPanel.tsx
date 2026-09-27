import { useState, useEffect, useRef } from 'react';
import { Search, CheckCircle, XCircle, AlertTriangle, Loader2, MinusCircle, Clock, Terminal, Copy, ChevronDown, ChevronRight, FileSearch, Archive, FileText } from 'lucide-react';
import type { DeviceInfo, ScanState, TimelineEntry } from '../api/client';
import { api } from '../api/client';

interface Props {
  device: DeviceInfo | null;
  scanId: string | undefined;
  scanState: ScanState | null;
  onStartScan: () => void;
  onCancelScan: () => void;
}

function StageIcon({ status }: { status: string }) {
  switch (status) {
    case 'completed': return <div className="stage-icon completed"><CheckCircle /></div>;
    case 'completed_with_warnings': return <div className="stage-icon warning"><AlertTriangle /></div>;
    case 'failed': return <div className="stage-icon failed"><XCircle /></div>;
    case 'running': return <div className="stage-icon running"><div className="pulse-ring" /><Loader2 className="spinner" /></div>;
    case 'skipped': return <div className="stage-icon skipped"><MinusCircle /></div>;
    default: return <div className="stage-icon pending"><Clock /></div>;
  }
}

function ElapsedTimer({ startedAt, isRunning }: { startedAt: string | null; isRunning: boolean }) {
  const [elapsed, setElapsed] = useState('00:00');

  useEffect(() => {
    if (!startedAt) return;
    const start = new Date(startedAt).getTime();

    const update = () => {
      const end = isRunning ? Date.now() : Date.now();
      const diff = Math.floor((end - start) / 1000);
      const m = Math.floor(diff / 60).toString().padStart(2, '0');
      const s = (diff % 60).toString().padStart(2, '0');
      setElapsed(`${m}:${s}`);
    };
    update();

    if (!isRunning) return;
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [startedAt, isRunning]);

  return <span className="text-mono">{elapsed}</span>;
}

function ForensicTerminal({ timeline, isRunning }: { timeline: TimelineEntry[]; isRunning: boolean }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [timeline, autoScroll]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const atBottom = scrollHeight - scrollTop - clientHeight < 20;
    setAutoScroll(atBottom);
  };

  const copyLogs = () => {
    const text = timeline.map(e => `${e.time}  [${e.level.padEnd(7)}]  ${e.message}`).join('\n');
    navigator.clipboard.writeText(text).catch(() => {});
  };

  const levelClass = (level: string) => {
    switch (level) {
      case 'SUCCESS': return 'term-success';
      case 'WARN': return 'term-warn';
      case 'ERROR': return 'term-error';
      default: return 'term-info';
    }
  };

  return (
    <div className="terminal-container">
      <div className="terminal-header" onClick={() => setExpanded(!expanded)} style={{ cursor: 'pointer' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <Terminal size={14} />
          <span className="terminal-title">Live Examination Activity</span>
          {isRunning && <span className="terminal-live-dot" />}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="terminal-btn" onClick={e => { e.stopPropagation(); copyLogs(); }} title="Copy logs">
            <Copy size={12} />
          </button>
        </div>
      </div>
      {expanded && (
        <div
          ref={scrollRef}
          className="terminal-body"
          onScroll={handleScroll}
        >
          {timeline.length === 0 ? (
            <div className="terminal-empty">Waiting for examination events...</div>
          ) : (
            timeline.map((entry, i) => (
              <div key={i} className={`terminal-line ${levelClass(entry.level)}`}>
                <span className="terminal-time">{entry.time}</span>
                <span className={`terminal-level ${levelClass(entry.level)}`}>{entry.level.padEnd(7)}</span>
                <span className="terminal-msg">{entry.message}</span>
              </div>
            ))
          )}
          {isRunning && (
            <div className="terminal-cursor">
              <span className="blink">_</span>
            </div>
          )}
        </div>
      )}
      {expanded && !autoScroll && isRunning && (
        <button className="terminal-scroll-btn" onClick={() => { setAutoScroll(true); if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; }}>
          Auto-scroll paused — click to resume
        </button>
      )}
    </div>
  );
}

export function ScanPanel({ device, scanId, scanState, onStartScan, onCancelScan }: Props) {
  const isRunning = scanState?.status === 'running';
  const isComplete = scanState && !isRunning && scanState.status !== 'pending';
  const stages = scanState?.stages || [];
  const timeline = scanState?.timeline || [];

  // Calculate duration
  const getDuration = () => {
    if (!scanState?.started_at) return null;
    const start = new Date(scanState.started_at).getTime();
    const end = scanState.completed_at ? new Date(scanState.completed_at).getTime() : Date.now();
    const diff = Math.floor((end - start) / 1000);
    const m = Math.floor(diff / 60);
    const s = diff % 60;
    return `${m}m ${s}s`;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1>Examination</h1>
          <p className="text-sm text-muted" style={{ marginTop: 4 }}>
            {isRunning ? 'Examination in progress...' : scanId ? `Examination ${scanId}` : 'Start a new forensic examination'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {isRunning && (
            <button className="btn btn-outline" style={{ color: 'var(--color-error)' }} onClick={onCancelScan}>
              Cancel
            </button>
          )}
          {device && !isRunning && (
            <button className="btn btn-primary" onClick={onStartScan}>
              <Search size={16} /> {scanId ? 'New Examination' : 'Start Examination'}
            </button>
          )}
        </div>
      </div>

      {/* No scan state */}
      {!scanId && !scanState && (
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: 48 }}>
            <Search size={40} color="var(--color-text-muted)" style={{ marginBottom: 12 }} />
            <p style={{ fontSize: '1rem', fontWeight: 500 }}>No Examination Started</p>
            <p className="text-sm text-muted" style={{ marginTop: 8, maxWidth: 400, margin: '8px auto' }}>
              {device ? 'Click "Start Examination" to begin a forensic analysis of the connected device.' : 'Connect a device first, then start an examination.'}
            </p>
          </div>
        </div>
      )}

      {/* Active Examination Header */}
      {scanState && (
        <div className={`exam-status-card ${isRunning ? 'running' : scanState.status}`}>
          <div className="exam-status-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div className={`exam-status-indicator ${scanState.status}`}>
                {isRunning ? <Loader2 className="spinner" size={20} /> :
                 scanState.status === 'completed' ? <CheckCircle size={20} /> :
                 scanState.status === 'failed' ? <XCircle size={20} /> :
                 <AlertTriangle size={20} />}
              </div>
              <div>
                <div className="exam-status-title">
                  {isRunning ? 'Examination In Progress' :
                   scanState.status === 'completed' ? 'Examination Completed' :
                   scanState.status === 'failed' ? 'Examination Failed' :
                   `Examination ${scanState.status.replace(/_/g, ' ')}`}
                </div>
                <div className="exam-status-subtitle">
                  {device && `${device.model || 'Unknown'} · ${device.manufacturer || ''} · Android ${device.android_version || '?'}`}
                </div>
              </div>
            </div>
            <div className="exam-status-meta">
              <div className="exam-meta-item">
                <span className="exam-meta-label">Elapsed</span>
                <ElapsedTimer startedAt={scanState.started_at} isRunning={isRunning} />
              </div>
              <div className="exam-meta-item">
                <span className="exam-meta-label">ID</span>
                <span className="text-mono text-xs">{scanState.scan_id.slice(-12)}</span>
              </div>
            </div>
          </div>

          {/* Current operation */}
          {isRunning && scanState.current_operation && (
            <div className="exam-current-op">
              <Loader2 className="spinner" size={14} />
              <span>{scanState.current_operation}</span>
            </div>
          )}
        </div>
      )}

      {/* Stage Pipeline */}
      {stages.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><Clock size={18} /> Examination Pipeline</div>
            <StatusBadge status={scanState?.status || 'unknown'} />
          </div>
          <div className="card-body" style={{ padding: '12px 16px' }}>
            <div className="stage-list">
              {stages.map((stage, idx) => (
                <div className={`stage-item ${stage.status === 'running' ? 'active' : ''}`} key={stage.stage_id}>
                  <div className="stage-number">{String(idx + 1).padStart(2, '0')}</div>
                  <StageIcon status={stage.status} />
                  <div style={{ flex: 1 }}>
                    <div className="stage-name">{stage.display_name}</div>
                    {stage.summary && <div className="stage-summary">{stage.summary}</div>}
                    {stage.error && <div className="stage-summary" style={{ color: 'var(--color-error)' }}>{stage.error}</div>}
                  </div>
                  {stage.duration_seconds != null && (
                    <span className="text-xs text-muted">{stage.duration_seconds.toFixed(1)}s</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Live Terminal */}
      {scanState && (
        <ForensicTerminal timeline={timeline} isRunning={isRunning} />
      )}

      {/* Completion Panel */}
      {isComplete && scanState && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              {scanState.status === 'completed' ? <CheckCircle size={18} color="var(--color-success)" /> :
               scanState.status === 'failed' ? <XCircle size={18} color="var(--color-error)" /> :
               <AlertTriangle size={18} color="var(--color-warning)" />}
              Examination Results
            </div>
          </div>
          <div className="card-body">
            <div className="completion-grid">
              <div className="completion-stat">
                <div className="completion-stat-value">{getDuration()}</div>
                <div className="completion-stat-label">Duration</div>
              </div>
              <div className="completion-stat">
                <div className="completion-stat-value">{scanState.findings_count}</div>
                <div className="completion-stat-label">Findings</div>
              </div>
              <div className="completion-stat">
                <div className="completion-stat-value">{stages.filter(s => s.status === 'completed').length}/{stages.length}</div>
                <div className="completion-stat-label">Stages</div>
              </div>
              <div className="completion-stat">
                <div className="completion-stat-value" style={{ textTransform: 'uppercase', fontSize: '0.75rem' }}>SHA-256</div>
                <div className="completion-stat-label">Integrity</div>
              </div>
            </div>
            <div className="completion-actions">
              <a href={api.getReportUrl(scanState.scan_id)} target="_blank" rel="noreferrer" className="btn btn-primary">
                <FileText size={16} /> Download Report
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Warnings */}
      {scanState && scanState.warnings.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><AlertTriangle size={18} /> Warnings</div>
          </div>
          <div className="card-body">
            {scanState.warnings.map((w, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 6, fontSize: '0.8125rem', color: 'var(--color-warning)' }}>
                <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 2 }} />
                <span>{w}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Technical Details */}
      {scanState && (
        <details className="card">
          <summary className="expandable-header" style={{ listStyle: 'none' }}>
            <span className="card-title" style={{ fontSize: '0.875rem' }}>Technical Details</span>
            <span className="text-xs text-muted">Click to expand</span>
          </summary>
          <div className="expandable-content">
            <div className="kv-grid">
              <span className="kv-label">Examination ID</span>
              <span className="kv-value text-mono text-sm">{scanState.scan_id}</span>
              <span className="kv-label">Profile</span>
              <span className="kv-value" style={{ textTransform: 'capitalize' }}>{scanState.scan_profile?.replace(/_/g, ' ') || 'Rapid Triage'}</span>
              <span className="kv-label">MVT Version</span>
              <span className="kv-value">{scanState.mvt_version || 'N/A'}</span>
              <span className="kv-label">ADB Version</span>
              <span className="kv-value">{scanState.adb_version || 'N/A'}</span>
              <span className="kv-label">Started</span>
              <span className="kv-value text-sm">{scanState.started_at ? new Date(scanState.started_at).toLocaleString() : 'N/A'}</span>
              <span className="kv-label">Completed</span>
              <span className="kv-value text-sm">{scanState.completed_at ? new Date(scanState.completed_at).toLocaleString() : isRunning ? 'In progress...' : 'N/A'}</span>
            </div>
          </div>
        </details>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const label = status.replace(/_/g, ' ');
  if (status === 'completed') return <span className="badge badge-success">{label}</span>;
  if (status === 'completed_with_warnings') return <span className="badge badge-warning">{label}</span>;
  if (status === 'partially_completed') return <span className="badge badge-warning">{label}</span>;
  if (status === 'failed') return <span className="badge badge-error">{label}</span>;
  if (status === 'running') return <span className="badge badge-info">{label}</span>;
  if (status === 'cancelled') return <span className="badge badge-neutral">{label}</span>;
  return <span className="badge badge-neutral">{label}</span>;
}
