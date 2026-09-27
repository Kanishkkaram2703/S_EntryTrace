import { Shield, Smartphone, Search, Archive, AlertTriangle, ChevronRight } from 'lucide-react';
import type { HealthResponse, DeviceInfo, ScanState, FindingSummary, Manifest } from '../api/client';

interface Props {
  health: HealthResponse | null;
  devices: DeviceInfo[];
  selectedDevice: DeviceInfo | null;
  scanState: ScanState | null;
  findings: FindingSummary | null;
  manifest: Manifest | null;
  onStartScan: () => void;
  onSelectTab: (tab: any) => void;
}

export function Dashboard({ health, devices, selectedDevice, scanState, findings, manifest, onStartScan, onSelectTab }: Props) {
  const connected = devices.find(d => d.state === 'connected');
  const engineReady = health?.mvt?.available && health?.adb?.available;
  const scanStatus = scanState?.status?.replace(/_/g, ' ') || 'None';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1>Overview</h1>
        <p className="text-secondary text-sm" style={{ marginTop: 4 }}>System status and examination summary</p>
      </div>

      {/* Status Cards */}
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-icon" style={{ background: connected ? 'var(--color-success-bg)' : '#f3f4f6', color: connected ? 'var(--color-success)' : '#9ca3af' }}>
            <Smartphone />
          </div>
          <div>
            <div className="stat-value">{connected ? connected.model || 'Connected' : 'None'}</div>
            <div className="stat-label">{connected ? `${connected.manufacturer || ''} · Android ${connected.android_version || '?'}` : 'No device connected'}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: engineReady ? 'var(--color-success-bg)' : 'var(--color-error-bg)', color: engineReady ? 'var(--color-success)' : 'var(--color-error)' }}>
            <Shield />
          </div>
          <div>
            <div className="stat-value">{engineReady ? 'Ready' : 'Error'}</div>
            <div className="stat-label">Forensic Engine{health?.mvt?.version ? ` · v${health.mvt.version}` : ''}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: scanState ? 'var(--color-info-bg)' : '#f3f4f6', color: scanState ? 'var(--color-info)' : '#9ca3af' }}>
            <Search />
          </div>
          <div>
            <div className="stat-value" style={{ textTransform: 'capitalize' }}>{scanStatus}</div>
            <div className="stat-label">Last Examination</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: manifest ? 'var(--color-success-bg)' : '#f3f4f6', color: manifest ? 'var(--color-success)' : '#9ca3af' }}>
            <Archive />
          </div>
          <div>
            <div className="stat-value">{manifest ? `${manifest.file_count} files` : 'None'}</div>
            <div className="stat-label">Evidence{manifest ? ` · ${fmt(manifest.total_bytes)}` : ''}</div>
          </div>
        </div>
      </div>

      {/* Findings summary if available */}
      {findings && findings.total > 0 && (
        <div className="card" onClick={() => onSelectTab('findings')} style={{ cursor: 'pointer' }}>
          <div className="card-header">
            <div className="card-title"><AlertTriangle size={18} /> Examination Results</div>
            <ChevronRight size={16} className="text-muted" />
          </div>
          <div className="card-body">
            <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{findings.total}</div>
                <div className="text-label">Total</div>
              </div>
              {Object.entries(findings.by_severity).map(([sev, count]) => (
                <div key={sev} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{count}</div>
                  <div className="text-label" style={{ textTransform: 'capitalize' }}>{sev}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Device section */}
      {connected ? (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><Smartphone size={18} /> Current Device</div>
            <button className="btn btn-outline" onClick={() => onSelectTab('device')}>
              View Details <ChevronRight size={14} />
            </button>
          </div>
          <div className="card-body">
            <div className="kv-grid">
              <span className="kv-label">Model</span>
              <span className="kv-value">{connected.model || 'Unknown'}</span>
              <span className="kv-label">Manufacturer</span>
              <span className="kv-value">{connected.manufacturer || 'Unknown'}</span>
              <span className="kv-label">Android Version</span>
              <span className="kv-value">{connected.android_version || 'Unknown'}</span>
              <span className="kv-label">Security Patch</span>
              <span className="kv-value">{connected.security_patch || 'Unknown'}</span>
              <span className="kv-label">Connection</span>
              <span className="kv-value"><span className="badge badge-success">Connected</span></span>
            </div>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><Smartphone size={18} /> Device Setup</div>
          </div>
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <p className="text-secondary text-sm">Connect an Android device to begin forensic examination.</p>
            <ol style={{ paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>
              <li>Open <strong>Settings</strong> on your Android device</li>
              <li>Navigate to <strong>About Phone</strong> and tap <strong>Build Number</strong> 7 times</li>
              <li>Go to <strong>Developer Options</strong> and enable <strong>USB Debugging</strong></li>
              <li>Connect the device via USB cable</li>
              <li>Accept the <strong>RSA fingerprint</strong> authorization prompt on the device</li>
            </ol>
          </div>
        </div>
      )}

      {/* Quick action */}
      {connected && engineReady && (
        <button className="btn btn-primary" onClick={onStartScan} style={{ alignSelf: 'flex-start', padding: '10px 24px' }}>
          <Search size={16} /> Start Examination
        </button>
      )}
    </div>
  );
}

function fmt(b: number): string {
  if (b > 1048576) return `${(b / 1048576).toFixed(1)} MB`;
  if (b > 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${b} B`;
}
