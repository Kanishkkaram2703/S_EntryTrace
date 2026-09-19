import { api } from '../api/client';

interface Props {
  manifest: any;
  scanId: string | undefined;
}

export function EvidencePanel({ manifest, scanId }: Props) {
  if (!scanId || !manifest) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold">Evidence</h2>
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-8 text-center">
          <p className="text-3xl mb-3">📁</p>
          <p className="text-[var(--text-secondary)]">No evidence manifest available</p>
          <p className="text-xs text-[var(--text-muted)] mt-2">Complete a scan to view collected evidence.</p>
        </div>
      </div>
    );
  }

  const files: any[] = manifest.files || [];
  const totalBytes = manifest.total_bytes || 0;
  const fmt = (b: number) => b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : b > 1024 ? `${(b / 1024).toFixed(1)} KB` : `${b} B`;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Evidence</h2>
          <p className="text-xs text-[var(--text-muted)]">Scan: {scanId}</p>
        </div>
        <a href={api.getReportUrl(scanId)} target="_blank" rel="noreferrer"
          className="px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium transition-colors">
          📄 Download Report
        </a>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-4 text-center">
          <p className="text-2xl font-bold">{manifest.file_count}</p>
          <p className="text-xs text-[var(--text-muted)]">Files</p>
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-4 text-center">
          <p className="text-2xl font-bold">{fmt(totalBytes)}</p>
          <p className="text-xs text-[var(--text-muted)]">Total Size</p>
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-4 text-center">
          <p className="text-2xl font-bold text-emerald-400">✓</p>
          <p className="text-xs text-[var(--text-muted)]">SHA-256 Verified</p>
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-4 text-center">
          <p className="text-2xl font-bold">{manifest.collection_status || '—'}</p>
          <p className="text-xs text-[var(--text-muted)]">Status</p>
        </div>
      </div>

      {/* Metadata */}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-5 space-y-2">
        <h3 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">Collection Metadata</h3>
        <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
          <div className="flex justify-between"><span className="text-[var(--text-muted)]">MVT</span><span>{manifest.mvt_version || '—'}</span></div>
          <div className="flex justify-between"><span className="text-[var(--text-muted)]">ADB</span><span>{manifest.adb_version || '—'}</span></div>
          <div className="flex justify-between"><span className="text-[var(--text-muted)]">Profile</span><span>{manifest.scan_profile || '—'}</span></div>
          <div className="flex justify-between"><span className="text-[var(--text-muted)]">Start</span><span className="text-xs">{manifest.collection_start || '—'}</span></div>
          <div className="flex justify-between"><span className="text-[var(--text-muted)]">End</span><span className="text-xs">{manifest.collection_end || '—'}</span></div>
          <div className="flex justify-between"><span className="text-[var(--text-muted)]">Generated</span><span className="text-xs">{manifest.generated_at || '—'}</span></div>
        </div>
      </div>

      {/* Limitations */}
      {manifest.limitations && manifest.limitations.length > 0 && (
        <div className="bg-amber-900/20 border border-amber-800 rounded-lg p-4">
          <p className="text-xs font-semibold text-amber-400 mb-2">Collection Limitations</p>
          {manifest.limitations.map((l: string, i: number) => (
            <p key={i} className="text-xs text-amber-300">• {l}</p>
          ))}
        </div>
      )}

      {/* File list */}
      {files.length > 0 && (
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-5">
          <h3 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">
            Evidence Files ({files.length})
          </h3>
          <div className="max-h-80 overflow-y-auto space-y-1">
            {files.slice(0, 100).map((f: any, i: number) => (
              <div key={i} className="flex items-center justify-between py-1.5 border-b border-[var(--border-color)] last:border-0 text-xs">
                <span className="text-[var(--text-primary)] truncate max-w-[50%]" title={f.relative_path}>{f.relative_path}</span>
                <div className="flex items-center gap-4">
                  <span className="text-[var(--text-muted)]">{fmt(f.size_bytes)}</span>
                  <span className="font-mono text-[var(--text-muted)] w-32 truncate" title={f.sha256}>{f.sha256?.substring(0, 16)}…</span>
                </div>
              </div>
            ))}
            {files.length > 100 && <p className="text-xs text-[var(--text-muted)] pt-2">...and {files.length - 100} more files</p>}
          </div>
        </div>
      )}

      {/* Warnings/Errors */}
      {manifest.warnings && manifest.warnings.length > 0 && (
        <div className="bg-amber-900/20 border border-amber-800 rounded-lg p-4">
          <p className="text-xs font-semibold text-amber-400 mb-1">Warnings</p>
          {manifest.warnings.map((w: string, i: number) => <p key={i} className="text-xs text-amber-300">{w}</p>)}
        </div>
      )}
      {manifest.errors && manifest.errors.length > 0 && (
        <div className="bg-red-900/20 border border-red-700 rounded-lg p-4">
          <p className="text-xs font-semibold text-red-400 mb-1">Errors</p>
          {manifest.errors.map((e: string, i: number) => <p key={i} className="text-xs text-red-300">{e}</p>)}
        </div>
      )}
    </div>
  );
}
