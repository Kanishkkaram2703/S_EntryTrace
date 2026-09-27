import { Archive, FileText, Hash, AlertTriangle, Info } from 'lucide-react';
import type { Manifest, ScanState } from '../api/client';

interface Props {
  manifest: Manifest | null;
  scanId: string | undefined;
  scanState: ScanState | null;
}

function fmt(b: number): string {
  if (b > 1048576) return `${(b / 1048576).toFixed(1)} MB`;
  if (b > 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${b} B`;
}

export function EvidencePanel({ manifest, scanId, scanState }: Props) {
  if (!scanId) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <h1>Evidence</h1>
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: 48 }}>
            <Archive size={40} color="var(--color-text-muted)" style={{ marginBottom: 12 }} />
            <p style={{ fontWeight: 500 }}>No Examination Selected</p>
            <p className="text-sm text-muted" style={{ marginTop: 8 }}>
              Select an examination from the History tab to view its evidence.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!manifest) {
    const isFailed = scanState?.status === 'failed';
    const isRunning = scanState?.status === 'running';
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <h1>Evidence</h1>
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: 48 }}>
            <Archive size={40} color="var(--color-text-muted)" style={{ marginBottom: 12 }} />
            <p style={{ fontWeight: 500 }}>No Evidence Collected</p>
            <p className="text-sm text-muted" style={{ marginTop: 8 }}>
              {isRunning
                ? 'Evidence is being collected. The manifest will be available after the examination completes.'
                : isFailed
                ? 'The examination failed before evidence could be fully collected and catalogued.'
                : 'Complete an examination to view evidence.'}
            </p>
            {isFailed && scanState?.warnings && scanState.warnings.length > 0 && (
              <div style={{ marginTop: 16, textAlign: 'left' }}>
                <p className="text-sm" style={{ fontWeight: 500, marginBottom: 8 }}>Collection issues:</p>
                {scanState.warnings.map((w, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 4, fontSize: '0.8125rem', color: 'var(--color-warning)' }}>
                    <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 2 }} />
                    <span>{w}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1>Evidence Collection</h1>
        <p className="text-sm text-muted" style={{ marginTop: 4 }}>
          Integrity-verified forensic artifacts for {scanId}
        </p>
      </div>

      {/* Summary stats */}
      <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'var(--color-info-bg)', color: 'var(--color-info)' }}>
            <FileText />
          </div>
          <div>
            <div className="stat-value">{manifest.file_count}</div>
            <div className="stat-label">Evidence Files</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'var(--color-success-bg)', color: 'var(--color-success)' }}>
            <Archive />
          </div>
          <div>
            <div className="stat-value">{fmt(manifest.total_bytes)}</div>
            <div className="stat-label">Total Size</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: '#f3f4f6', color: '#6b7280' }}>
            <Hash />
          </div>
          <div>
            <div className="stat-value">SHA-256</div>
            <div className="stat-label">Hash Algorithm</div>
          </div>
        </div>
      </div>

      {/* Collection Info */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><Info size={18} /> Collection Information</div>
        </div>
        <div className="card-body">
          <div className="kv-grid">
            <span className="kv-label">Scan ID</span>
            <span className="kv-value text-mono text-sm">{manifest.scan_id}</span>
            <span className="kv-label">Profile</span>
            <span className="kv-value">{manifest.scan_profile || 'Rapid Triage'}</span>
            <span className="kv-label">MVT Version</span>
            <span className="kv-value">{manifest.mvt_version || 'N/A'}</span>
            <span className="kv-label">ADB Version</span>
            <span className="kv-value">{manifest.adb_version || 'N/A'}</span>
            <span className="kv-label">Collection Start</span>
            <span className="kv-value text-sm">{manifest.collection_start ? new Date(manifest.collection_start).toLocaleString() : 'N/A'}</span>
            <span className="kv-label">Collection End</span>
            <span className="kv-value text-sm">{manifest.collection_end ? new Date(manifest.collection_end).toLocaleString() : 'N/A'}</span>
            <span className="kv-label">Manifest Generated</span>
            <span className="kv-value text-sm">{manifest.generated_at ? new Date(manifest.generated_at).toLocaleString() : 'N/A'}</span>
          </div>
        </div>
      </div>

      {/* Warnings */}
      {manifest.warnings && manifest.warnings.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><AlertTriangle size={18} /> Collection Warnings</div>
          </div>
          <div className="card-body">
            {manifest.warnings.map((w, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 6, fontSize: '0.8125rem', color: 'var(--color-warning)' }}>
                <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 2 }} />
                <span>{w}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Limitations */}
      {manifest.limitations && manifest.limitations.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><Info size={18} /> Limitations</div>
          </div>
          <div className="card-body">
            {manifest.limitations.map((l, i) => (
              <div key={i} style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)', marginBottom: 4, paddingLeft: 12, borderLeft: '2px solid var(--color-border)' }}>
                {l}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* File Inventory */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><Hash size={18} /> Evidence File Inventory</div>
        </div>
        <div className="card-body" style={{ padding: '12px 16px', overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--color-border)' }}>
                <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, color: 'var(--color-text-muted)' }}>File</th>
                <th style={{ textAlign: 'right', padding: '6px 8px', fontWeight: 600, color: 'var(--color-text-muted)' }}>Size</th>
                <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, color: 'var(--color-text-muted)' }}>SHA-256</th>
              </tr>
            </thead>
            <tbody>
              {manifest.files.slice(0, 50).map((f, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--color-border-light)' }}>
                  <td style={{ padding: '5px 8px' }} className="text-mono">{f.relative_path}</td>
                  <td style={{ padding: '5px 8px', textAlign: 'right', whiteSpace: 'nowrap' }}>{fmt(f.size_bytes)}</td>
                  <td style={{ padding: '5px 8px' }} className="text-mono">{f.sha256?.slice(0, 16)}...</td>
                </tr>
              ))}
            </tbody>
          </table>
          {manifest.files.length > 50 && (
            <p className="text-xs text-muted" style={{ marginTop: 8 }}>
              Showing 50 of {manifest.files.length} files.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
