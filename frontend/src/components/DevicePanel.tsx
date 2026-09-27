import { Smartphone, RefreshCw, Clock, CheckCircle, AlertCircle, Info } from 'lucide-react';
import type { DeviceInfo } from '../api/client';

interface Props {
  device: DeviceInfo | null;
  devices: DeviceInfo[];
  onSelect: (d: DeviceInfo) => void;
  onRefresh: () => void;
}

export function DevicePanel({ device, devices, onSelect, onRefresh }: Props) {
  if (!device && devices.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <h1>Device</h1>
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: 48 }}>
            <Smartphone size={40} color="var(--color-text-muted)" style={{ marginBottom: 12 }} />
            <p style={{ fontSize: '1rem', fontWeight: 500 }}>No Device Connected</p>
            <p className="text-sm text-muted" style={{ marginTop: 8, maxWidth: 400, margin: '8px auto' }}>
              Connect an Android device with USB debugging enabled to begin.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const d = device || devices[0];
  const metaState = d.metadata_state || 'unavailable';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1>Device Profile</h1>
          <p className="text-sm text-muted" style={{ marginTop: 4 }}>
            {d.manufacturer} {d.model} · {d.serial}
          </p>
        </div>
        <button className="btn btn-outline" onClick={onRefresh}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Multiple device selector */}
      {devices.length > 1 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">Connected Devices ({devices.length})</div>
          </div>
          <div className="card-body" style={{ display: 'flex', gap: 8 }}>
            {devices.map(dev => (
              <button
                key={dev.serial}
                className={`btn ${dev.serial === d.serial ? 'btn-primary' : 'btn-outline'}`}
                onClick={() => onSelect(dev)}
              >
                {dev.model || dev.serial}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Metadata state indicator */}
      {metaState === 'stale' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: 'var(--color-warning-bg)', borderRadius: 'var(--radius)', fontSize: '0.8125rem', color: 'var(--color-warning)' }}>
          <Clock size={14} />
          <span>Device information may be stale. Some properties could not be refreshed.</span>
        </div>
      )}
      {metaState === 'error' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: 'var(--color-error-bg)', borderRadius: 'var(--radius)', fontSize: '0.8125rem', color: 'var(--color-error)' }}>
          <AlertCircle size={14} />
          <span>Unable to read device properties. Showing last verified values.</span>
        </div>
      )}

      {/* Device Info */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><Smartphone size={18} /> Device Information</div>
          <span className={`badge ${d.state === 'connected' ? 'badge-success' : d.state === 'unauthorized' ? 'badge-warning' : 'badge-error'}`}>
            {d.state}
          </span>
        </div>
        <div className="card-body">
          <div className="kv-grid">
            <span className="kv-label">Model</span>
            <span className="kv-value">{d.model || 'Not available'}</span>
            <span className="kv-label">Manufacturer</span>
            <span className="kv-value">{d.manufacturer || 'Not available'}</span>
            <span className="kv-label">Android Version</span>
            <span className="kv-value">{d.android_version || 'Not available'}</span>
            <span className="kv-label">SDK / API Level</span>
            <span className="kv-value">{d.sdk_level || 'Not available'}</span>
            <span className="kv-label">Security Patch</span>
            <span className="kv-value">{d.security_patch || 'Not available'}</span>
            <span className="kv-label">Build Fingerprint</span>
            <span className="kv-value text-mono text-xs">{d.build_fingerprint || 'Not available'}</span>
            <span className="kv-label">Serial Number</span>
            <span className="kv-value text-mono text-sm">{d.serial}</span>
            <span className="kv-label">Root Status</span>
            <span className="kv-value">{d.is_rooted === true ? 'Rooted' : d.is_rooted === false ? 'Not rooted' : 'Unknown'}</span>
            <span className="kv-label">Connection</span>
            <span className="kv-value">{d.state}</span>
          </div>
        </div>
      </div>

      {/* Verification info */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><Info size={18} /> Verification</div>
        </div>
        <div className="card-body">
          <div className="kv-grid">
            <span className="kv-label">Metadata State</span>
            <span className="kv-value">
              <span className={`badge ${metaState === 'verified' ? 'badge-success' : metaState === 'stale' ? 'badge-warning' : 'badge-neutral'}`}>
                {metaState}
              </span>
            </span>
            <span className="kv-label">Last Verified</span>
            <span className="kv-value text-sm">
              {d.last_verified_at ? new Date(d.last_verified_at).toLocaleString() : 'Not yet verified'}
            </span>
            <span className="kv-label">First Detected</span>
            <span className="kv-value text-sm">{new Date(d.detected_at).toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* Technical Details */}
      <details className="card">
        <summary className="expandable-header" style={{ listStyle: 'none' }}>
          <span className="card-title" style={{ fontSize: '0.875rem' }}>Technical Details</span>
          <span className="text-xs text-muted">Click to expand</span>
        </summary>
        <div className="expandable-content">
          <div className="kv-grid">
            <span className="kv-label">ADB Version</span>
            <span className="kv-value text-mono text-sm">{d.adb_version || 'N/A'}</span>
          </div>
        </div>
      </details>
    </div>
  );
}
