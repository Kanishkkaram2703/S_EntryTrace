import { useState, useEffect, useCallback, useRef } from 'react';
import { LayoutDashboard, Smartphone, Search, FileSearch, Archive, FileText, Loader2, History, Download, RefreshCw, Eye, ArrowLeft, AlertCircle, CheckCircle } from 'lucide-react';
import './index.css';
import { api } from './api/client';
import type { HealthResponse, DeviceInfo, ScanState, FindingSummary, Manifest, ScanListItem } from './api/client';
import { Dashboard } from './components/Dashboard';
import { DevicePanel } from './components/DevicePanel';
import { ScanPanel } from './components/ScanPanel';
import { FindingsPanel } from './components/FindingsPanel';
import { EvidencePanel } from './components/EvidencePanel';

type Tab = 'overview' | 'device' | 'scan' | 'findings' | 'evidence' | 'reports' | 'history';

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'overview', label: 'Overview', icon: <LayoutDashboard /> },
  { id: 'device', label: 'Device', icon: <Smartphone /> },
  { id: 'scan', label: 'Examination', icon: <Search /> },
  { id: 'findings', label: 'Findings', icon: <FileSearch /> },
  { id: 'evidence', label: 'Evidence', icon: <Archive /> },
  { id: 'reports', label: 'Reports', icon: <FileText /> },
  { id: 'history', label: 'History', icon: <History /> },
];

export default function App() {
  const [tab, setTab] = useState<Tab>('overview');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<DeviceInfo | null>(null);

  // Multi-examination state
  const [examHistory, setExamHistory] = useState<ScanListItem[]>([]);
  const [selectedExamId, setSelectedExamId] = useState<string | undefined>(undefined);
  const [scanState, setScanState] = useState<ScanState | null>(null);
  const [findings, setFindings] = useState<FindingSummary | null>(null);
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [loading, setLoading] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load examination data for a specific exam ID
  const loadExamData = useCallback(async (examId: string) => {
    const [state, f, m] = await Promise.all([
      api.getScan(examId).catch(() => null),
      api.getFindings(examId).catch(() => null),
      api.getManifest(examId).catch(() => null),
    ]);
    if (state) setScanState(state);
    if (f) setFindings(f);
    if (m) setManifest(m);
  }, []);

  // Refresh examination history
  const refreshHistory = useCallback(async () => {
    try {
      const result = await api.listScans();
      setExamHistory(result.scans || []);
      return result.scans || [];
    } catch {
      return [];
    }
  }, []);

  // Initial load
  useEffect(() => {
    const init = async () => {
      try {
        const [h, d] = await Promise.all([api.health(), api.listDevices()]);
        setHealth(h);
        setDevices(d.devices);
        if (d.devices.length === 1) setSelectedDevice(d.devices[0]);

        // Load examination history
        const scans = await refreshHistory();
        if (scans.length > 0) {
          const latest = scans[scans.length - 1];
          setSelectedExamId(latest.scan_id);
          await loadExamData(latest.scan_id);
        }
      } catch (e) {
        console.error('Init failed:', e);
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  // Periodic device refresh
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const d = await api.listDevices();
        setDevices(d.devices);
        if (d.devices.length === 1 && !selectedDevice) setSelectedDevice(d.devices[0]);
        if (selectedDevice) {
          const updated = d.devices.find(dev => dev.serial === selectedDevice.serial);
          if (updated) setSelectedDevice(updated);
        }
      } catch { /* ignore refresh errors */ }
    }, 5000);
    return () => clearInterval(interval);
  }, [selectedDevice]);

  // Scan polling — polls while examination is running
  useEffect(() => {
    if (!selectedExamId || scanState?.status !== 'running') {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }
    pollRef.current = setInterval(async () => {
      try {
        const state = await api.getScan(selectedExamId);
        setScanState(state);
        if (state.status !== 'running') {
          const [f, m] = await Promise.all([
            api.getFindings(selectedExamId).catch(() => null),
            api.getManifest(selectedExamId).catch(() => null),
          ]);
          if (f) setFindings(f);
          if (m) setManifest(m);
          if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
          // Refresh history after completion
          refreshHistory();
        }
      } catch { /* ignore poll errors */ }
    }, 2000);
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [selectedExamId, scanState?.status]);

  const handleStartScan = useCallback(async () => {
    if (!selectedDevice) return;
    try {
      const result = await api.startScan(selectedDevice.serial);
      if (result.scan_id) {
        setSelectedExamId(result.scan_id);
        setScanState(null);
        setFindings(null);
        setManifest(null);
        setTab('scan');
        // Start polling immediately
        setTimeout(async () => {
          try {
            const state = await api.getScan(result.scan_id);
            setScanState(state);
          } catch { /* ignore */ }
        }, 500);
      }
    } catch (e) {
      console.error('Scan start failed:', e);
    }
  }, [selectedDevice]);

  const handleSelectExam = useCallback(async (examId: string) => {
    setSelectedExamId(examId);
    setScanState(null);
    setFindings(null);
    setManifest(null);
    await loadExamData(examId);
  }, [loadExamData]);

  const handleRefreshDevice = useCallback(async () => {
    if (!selectedDevice) return;
    try {
      const info = await api.getDevice(selectedDevice.serial);
      setSelectedDevice(info);
    } catch { /* ignore */ }
  }, [selectedDevice]);

  const handleCancelScan = useCallback(async () => {
    if (!selectedExamId) return;
    try {
      await api.cancelScan(selectedExamId);
    } catch { /* ignore */ }
  }, [selectedExamId]);

  const engineReady = health?.mvt?.available && health?.adb?.available;

  if (loading) {
    return (
      <div className="app-container" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <Loader2 className="spinner" size={32} color="#2563eb" />
        <p className="text-muted" style={{ marginTop: 12 }}>Connecting to S*EntryTrace...</p>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-top">
          <div className="brand">
            <div>
              <div className="brand-name">S*EntryTrace</div>
              <div className="brand-subtitle">Android Digital Forensics Workstation</div>
            </div>
          </div>
          <div className="system-status">
            <span>
              <span className={`status-dot ${engineReady ? 'ok' : 'err'}`} />
              {engineReady ? 'System Ready' : 'System Error'}
            </span>
            <span>
              <span className={`status-dot ${devices.some(d => d.state === 'connected') ? 'ok' : 'warn'}`} />
              {devices.some(d => d.state === 'connected') ? 'Device Connected' : 'No Device'}
            </span>
          </div>
        </div>
        <nav className="nav-tabs">
          {TABS.map(t => (
            <button
              key={t.id}
              className={`nav-tab ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Content */}
      <main className="main-content">
        {tab === 'overview' && (
          <Dashboard
            health={health}
            devices={devices}
            selectedDevice={selectedDevice}
            scanState={scanState}
            findings={findings}
            manifest={manifest}
            onStartScan={handleStartScan}
            onSelectTab={setTab}
          />
        )}
        {tab === 'device' && (
          <DevicePanel
            device={selectedDevice}
            devices={devices}
            onSelect={setSelectedDevice}
            onRefresh={handleRefreshDevice}
          />
        )}
        {tab === 'scan' && (
          <ScanPanel
            device={selectedDevice}
            scanId={selectedExamId}
            scanState={scanState}
            onStartScan={handleStartScan}
            onCancelScan={handleCancelScan}
          />
        )}
        {tab === 'findings' && (
          <FindingsPanel findings={findings} scanId={selectedExamId} scanState={scanState} />
        )}
        {tab === 'evidence' && (
          <EvidencePanel manifest={manifest} scanId={selectedExamId} scanState={scanState} />
        )}
        {tab === 'reports' && (
          <ReportsPage examId={selectedExamId} scanState={scanState} />
        )}
        {tab === 'history' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h1>Examination History</h1>
                <p className="text-sm text-muted" style={{ marginTop: 4 }}>All forensic examinations performed</p>
              </div>
              <button className="btn btn-outline" onClick={refreshHistory}>Refresh</button>
            </div>
            {examHistory.length === 0 ? (
              <div className="card">
                <div className="card-body" style={{ textAlign: 'center', padding: 48 }}>
                  <History size={40} color="var(--color-text-muted)" style={{ marginBottom: 12 }} />
                  <p style={{ fontWeight: 500 }}>No Examinations</p>
                  <p className="text-sm text-muted" style={{ marginTop: 8 }}>Start an examination to see it here.</p>
                </div>
              </div>
            ) : (
              <div className="card">
                <div className="card-body" style={{ padding: '12px 16px', overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '2px solid var(--color-border)' }}>
                        <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: 'var(--color-text-muted)' }}>Examination ID</th>
                        <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: 'var(--color-text-muted)' }}>Device</th>
                        <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: 'var(--color-text-muted)' }}>Date/Time</th>
                        <th style={{ textAlign: 'left', padding: '8px', fontWeight: 600, color: 'var(--color-text-muted)' }}>Status</th>
                        <th style={{ textAlign: 'center', padding: '8px', fontWeight: 600, color: 'var(--color-text-muted)' }}>Findings</th>
                        <th style={{ textAlign: 'center', padding: '8px', fontWeight: 600, color: 'var(--color-text-muted)' }}>Report</th>
                        <th style={{ padding: '8px' }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...examHistory].reverse().map(exam => (
                        <tr
                          key={exam.scan_id}
                          style={{
                            borderBottom: '1px solid var(--color-border-light)',
                            background: exam.scan_id === selectedExamId ? 'var(--color-accent-light)' : 'transparent',
                            cursor: 'pointer',
                          }}
                          onClick={() => { handleSelectExam(exam.scan_id); setTab('scan'); }}
                        >
                          <td className="text-mono" style={{ padding: '8px', fontSize: '0.75rem' }}>
                            {exam.scan_id.length > 30 ? '...' + exam.scan_id.slice(-20) : exam.scan_id}
                          </td>
                          <td style={{ padding: '8px' }}>{exam.device_model || exam.device_serial || 'Unknown'}</td>
                          <td style={{ padding: '8px' }}>{exam.started_at ? new Date(exam.started_at).toLocaleString() : 'N/A'}</td>
                          <td style={{ padding: '8px' }}>
                            <StatusBadge status={exam.status} />
                          </td>
                          <td style={{ padding: '8px', textAlign: 'center' }}>{exam.findings_count || 0}</td>
                          <td style={{ padding: '8px', textAlign: 'center' }}>
                            {exam.has_report ? (
                              <a
                                href={api.getReportUrl(exam.scan_id)}
                                target="_blank"
                                rel="noreferrer"
                                className="text-sm"
                                style={{ color: 'var(--color-accent)' }}
                                onClick={e => e.stopPropagation()}
                              >
                                PDF
                              </a>
                            ) : '—'}
                          </td>
                          <td style={{ padding: '8px' }}>
                            <button
                              className="btn btn-outline"
                              style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                              onClick={e => { e.stopPropagation(); handleSelectExam(exam.scan_id); setTab('scan'); }}
                            >
                              View
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

function ReportsPage({ examId, scanState }: { examId: string | undefined; scanState: ScanState | null }) {
  const [reportStatus, setReportStatus] = useState<{ exists: boolean; status: string; size_bytes: number } | null>(null);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [pdfKey, setPdfKey] = useState(0); // Force iframe reload on regeneration

  // Check report status whenever examId changes
  useEffect(() => {
    if (!examId) { setReportStatus(null); return; }
    setViewerOpen(false);
    setError('');
    api.getReportStatus(examId)
      .then(s => setReportStatus(s))
      .catch(() => setReportStatus(null));
  }, [examId]);

  const handleGenerate = async () => {
    if (!examId) return;
    setGenerating(true);
    setError('');
    try {
      const result = await api.generateReport(examId);
      setReportStatus({ exists: true, status: 'available', size_bytes: result.size_bytes || 0 });
      setPdfKey(k => k + 1);
    } catch (e) {
      setError('Report generation failed. Check backend logs.');
    } finally {
      setGenerating(false);
    }
  };

  if (!examId) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <h1>Reports</h1>
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: 48 }}>
            <FileText size={40} color="var(--color-text-muted)" style={{ marginBottom: 12 }} />
            <p style={{ fontWeight: 500 }}>No Examination Selected</p>
            <p className="text-sm text-muted" style={{ marginTop: 8 }}>Select an examination from the History tab to manage reports.</p>
          </div>
        </div>
      </div>
    );
  }

  const isAvailable = reportStatus?.exists && reportStatus.status === 'available';
  const statusLabel = reportStatus?.status === 'available' ? 'Available'
    : reportStatus?.status === 'failed' ? 'Failed'
    : 'Not Generated';
  const statusClass = reportStatus?.status === 'available' ? 'badge-success'
    : reportStatus?.status === 'failed' ? 'badge-error'
    : 'badge-neutral';

  // PDF Viewer mode
  if (viewerOpen && isAvailable) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Viewer Header */}
        <div className="card" style={{ padding: '12px 16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: '1rem' }}>S*EntryTrace</div>
              <div className="text-sm text-muted">Android Digital Forensics Examination Report</div>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span className="text-mono text-xs text-muted">{examId.slice(-20)}</span>
              <a href={api.getReportPdfUrl(examId)} download className="btn btn-outline" style={{ padding: '6px 12px', fontSize: '0.8125rem' }}>
                <Download size={14} /> Download PDF
              </a>
              <button className="btn btn-outline" style={{ padding: '6px 12px', fontSize: '0.8125rem' }} onClick={() => setViewerOpen(false)}>
                <ArrowLeft size={14} /> Back to Reports
              </button>
            </div>
          </div>
        </div>
        {/* PDF iframe */}
        <div style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden', background: '#525659', minHeight: 'calc(100vh - 220px)' }}>
          <iframe
            key={pdfKey}
            src={api.getReportPdfUrl(examId)}
            style={{ width: '100%', height: 'calc(100vh - 220px)', border: 'none' }}
            title="S*EntryTrace Forensic Report"
          />
        </div>
      </div>
    );
  }

  // Reports dashboard
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1>Reports</h1>
        <p className="text-sm text-muted" style={{ marginTop: 4 }}>Forensic examination report management</p>
      </div>

      {/* Report Info */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><FileText size={18} /> Report Details</div>
          <span className={`badge ${statusClass}`}>Report {statusLabel}</span>
        </div>
        <div className="card-body">
          <div className="kv-grid">
            <span className="kv-label">Examination ID</span>
            <span className="kv-value text-mono text-sm">{examId}</span>
            <span className="kv-label">Examination Status</span>
            <span className="kv-value">{scanState?.status?.replace(/_/g, ' ') || 'Unknown'}</span>
            <span className="kv-label">Report Status</span>
            <span className="kv-value">
              {isAvailable ? (
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <CheckCircle size={14} color="var(--color-success)" /> Available
                  {reportStatus.size_bytes > 0 && <span className="text-xs text-muted">({(reportStatus.size_bytes / 1024).toFixed(0)} KB)</span>}
                </span>
              ) : (
                <span style={{ color: 'var(--color-text-muted)' }}>{statusLabel}</span>
              )}
            </span>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="card" style={{ borderColor: 'var(--color-error)' }}>
          <div className="card-body" style={{ display: 'flex', gap: 8, alignItems: 'center', color: 'var(--color-error)' }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Actions</div>
        </div>
        <div className="card-body">
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {/* View Report */}
            <button
              className="btn btn-primary"
              disabled={!isAvailable}
              onClick={() => setViewerOpen(true)}
              style={{ minWidth: 150 }}
            >
              <Eye size={16} /> View Report
            </button>

            {/* Download Report */}
            {isAvailable ? (
              <a href={api.getReportPdfUrl(examId)} download className="btn btn-outline" style={{ minWidth: 150 }}>
                <Download size={16} /> Download Report
              </a>
            ) : (
              <button className="btn btn-outline" disabled style={{ minWidth: 150 }}>
                <Download size={16} /> Download Report
              </button>
            )}

            {/* Regenerate Report */}
            <button
              className="btn btn-outline"
              disabled={generating}
              onClick={handleGenerate}
              style={{ minWidth: 150 }}
            >
              {generating ? <Loader2 className="spinner" size={16} /> : <RefreshCw size={16} />}
              {generating ? 'Generating...' : (isAvailable ? 'Regenerate Report' : 'Generate Report')}
            </button>
          </div>

          {!isAvailable && !generating && (
            <p className="text-sm text-muted" style={{ marginTop: 12 }}>
              {scanState?.status === 'running'
                ? 'The examination is still in progress. The report will be generated automatically upon completion.'
                : 'Generate the report to view or download the forensic examination PDF.'}
            </p>
          )}
        </div>
      </div>
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
