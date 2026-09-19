import { useState, useEffect } from 'react';
import { api, type DeviceInfo, type ScanInfo } from '../api/client';

interface Props {
  scan: ScanInfo | null;
  onStart: () => void;
  selectedDevice: DeviceInfo | null;
}

export function ScanPanel({ scan, onStart, selectedDevice }: Props) {
  const [logs, setLogs] = useState('');
  const [cancelling, setCancelling] = useState(false);

  // Poll logs during scan
  useEffect(() => {
    if (!scan || (scan.status !== 'running' && scan.status !== 'completed' && scan.status !== 'failed')) return;
    const fetchLogs = async () => {
      try {
        const l = await api.getScanLogs(scan.scan_id);
        setLogs(l.logs);
      } catch { /* ignore */ }
    };
    fetchLogs();
    if (scan.status === 'running') {
      const iv = setInterval(fetchLogs, 2000);
      return () => clearInterval(iv);
    }
  }, [scan?.scan_id, scan?.status]);

  const handleCancel = async () => {
    if (!scan) return;
    setCancelling(true);
    try { await api.cancelScan(scan.scan_id); } catch { /* ignore */ }
    setCancelling(false);
  };

  if (!scan) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold">Scan</h2>
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-8 text-center">
          {selectedDevice && selectedDevice.state === 'connected' ? (
            <>
              <p className="text-3xl mb-3">🔍</p>
              <p className="text-[var(--text-secondary)]">Ready to scan</p>
              <p className="text-xs text-[var(--text-muted)] mt-2 mb-4">
                Rapid Triage will collect a bugreport and analyze it with MVT.
              </p>
              <button onClick={onStart}
                className="px-6 py-2.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium text-sm transition-colors">
                Start Rapid Triage
              </button>
            </>
          ) : (
            <>
              <p className="text-3xl mb-3">📱</p>
              <p className="text-[var(--text-secondary)]">No scan available</p>
              <p className="text-xs text-[var(--text-muted)] mt-2">
                Connect and select an authorized Android device to begin scanning.
              </p>
            </>
          )}
        </div>
      </div>
    );
  }

  const isRunning = scan.status === 'running';
  const elapsed = scan.started_at ? Math.floor((Date.now() - new Date(scan.started_at).getTime()) / 1000) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Scan Progress</h2>
          <p className="text-xs text-[var(--text-muted)]">{scan.scan_id}</p>
        </div>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${
          scan.status === 'completed' ? 'bg-emerald-500/15 text-emerald-400' :
          scan.status === 'running' ? 'bg-cyan-500/15 text-cyan-400' :
          scan.status === 'failed' ? 'bg-red-500/15 text-red-400' :
          scan.status === 'cancelled' ? 'bg-gray-500/15 text-gray-400' :
          'bg-amber-500/15 text-amber-400'
        }`}>{scan.status}</span>
      </div>

      {/* Info */}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-5 space-y-3">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-xs text-[var(--text-muted)] block">Device</span>
            <span>{scan.device_serial}</span>
          </div>
          <div>
            <span className="text-xs text-[var(--text-muted)] block">Profile</span>
            <span>Rapid Triage</span>
          </div>
          <div>
            <span className="text-xs text-[var(--text-muted)] block">Elapsed</span>
            <span>{isRunning ? `${elapsed}s` : scan.completed_at ? 'Done' : '—'}</span>
          </div>
          <div>
            <span className="text-xs text-[var(--text-muted)] block">Operation</span>
            <span className="text-xs">{scan.current_operation || '—'}</span>
          </div>
        </div>

        {isRunning && (
          <div className="w-full h-1 bg-[var(--bg-secondary)] rounded-full overflow-hidden">
            <div className="h-full bg-cyan-500 rounded-full animate-pulse" style={{ width: '100%' }}></div>
          </div>
        )}
      </div>

      {/* Warnings/Errors */}
      {scan.warnings && scan.warnings.length > 0 && (
        <div className="bg-amber-900/30 border border-amber-700 rounded-lg p-4">
          <p className="text-xs font-semibold text-amber-400 mb-1">Warnings</p>
          {scan.warnings.map((w, i) => <p key={i} className="text-xs text-amber-300">{w}</p>)}
        </div>
      )}
      {scan.errors && scan.errors.length > 0 && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4">
          <p className="text-xs font-semibold text-red-400 mb-1">Errors</p>
          {scan.errors.map((e, i) => <p key={i} className="text-xs text-red-300">{e}</p>)}
        </div>
      )}

      {/* Logs */}
      <div>
        <h3 className="text-sm font-semibold text-[var(--text-secondary)] mb-2">Scan Logs</h3>
        <div className="log-output">{logs || (isRunning ? 'Waiting for log output...' : 'No logs available.')}</div>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        {isRunning && (
          <button onClick={handleCancel} disabled={cancelling}
            className="px-4 py-2 rounded-lg border border-red-600 text-red-400 text-sm hover:bg-red-900/30 transition-colors disabled:opacity-50">
            {cancelling ? 'Cancelling...' : 'Cancel Scan'}
          </button>
        )}
        {scan.status === 'completed' && (
          <a href={api.getReportUrl(scan.scan_id)} target="_blank" rel="noreferrer"
            className="px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium transition-colors">
            📄 Download Report
          </a>
        )}
      </div>
    </div>
  );
}
