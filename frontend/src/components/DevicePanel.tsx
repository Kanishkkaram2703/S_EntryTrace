import type { DeviceInfo } from '../api/client';

function InfoRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-[var(--border-color)] last:border-0">
      <span className="text-xs text-[var(--text-muted)] uppercase tracking-wider">{label}</span>
      <span className="text-sm text-[var(--text-primary)]">{value ?? 'Unknown'}</span>
    </div>
  );
}

interface Props {
  device: DeviceInfo | null;
  devices: DeviceInfo[];
  onSelect: (d: DeviceInfo) => void;
  onStartScan: () => void;
}

export function DevicePanel({ device, devices, onSelect, onStartScan }: Props) {
  if (!device) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold">Device Information</h2>
        {devices.length === 0 ? (
          <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-8 text-center">
            <p className="text-3xl mb-3">📱</p>
            <p className="text-lg text-[var(--text-secondary)]">No Android device connected</p>
            <p className="text-xs text-[var(--text-muted)] mt-2 max-w-md mx-auto">
              Connect an Android device via USB cable. Ensure USB Debugging is enabled in Developer Options, then authorize the connection when prompted on the device screen.
            </p>
          </div>
        ) : (
          <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-5">
            <h3 className="text-sm font-semibold text-[var(--text-secondary)] mb-3">Select a device</h3>
            {devices.map(d => (
              <button key={d.serial} onClick={() => onSelect(d)}
                className="w-full p-3 mb-2 rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--bg-card-hover)] transition-colors text-left">
                <span className="text-sm">{d.model || d.serial}</span>
                <span className={`ml-2 px-2 py-0.5 rounded text-xs ${
                  d.state === 'connected' ? 'bg-emerald-500/15 text-emerald-400' :
                  d.state === 'unauthorized' ? 'bg-amber-500/15 text-amber-400' :
                  'bg-red-500/15 text-red-400'}`}>{d.state}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  const stateColor = device.state === 'connected' ? 'text-emerald-400' :
    device.state === 'unauthorized' ? 'text-amber-400' : 'text-red-400';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">{device.model || 'Android Device'}</h2>
          <p className="text-sm text-[var(--text-muted)]">{device.manufacturer || ''} · {device.serial}</p>
        </div>
        <span className={`px-3 py-1 rounded-full text-sm font-medium ${stateColor} ${
          device.state === 'connected' ? 'bg-emerald-500/15' :
          device.state === 'unauthorized' ? 'bg-amber-500/15' : 'bg-red-500/15'}`}>{device.state}</span>
      </div>

      {device.state === 'unauthorized' && (
        <div className="bg-amber-900/30 border border-amber-700 rounded-lg p-4 text-sm text-amber-300">
          ⚠ This device has not authorized USB debugging. Please check the device screen and tap "Allow USB debugging."
        </div>
      )}

      {device.state === 'offline' && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-sm text-red-300">
          ⚠ This device is offline. Try reconnecting the USB cable or restarting the ADB server.
        </div>
      )}

      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-5">
        <h3 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">Device Metadata</h3>
        <InfoRow label="Serial" value={device.serial} />
        <InfoRow label="Model" value={device.model} />
        <InfoRow label="Manufacturer" value={device.manufacturer} />
        <InfoRow label="Android Version" value={device.android_version} />
        <InfoRow label="SDK / API Level" value={device.sdk_level} />
        <InfoRow label="Security Patch" value={device.security_patch} />
        <InfoRow label="Build Fingerprint" value={device.build_fingerprint} />
        <InfoRow label="Root Status" value={device.is_rooted === null ? 'Unknown' : device.is_rooted ? 'Rooted' : 'Not Rooted'} />
        <InfoRow label="ADB Version" value={device.adb_version} />
        <InfoRow label="Detected At" value={device.detected_at} />
      </div>

      {device.state === 'connected' && (
        <button onClick={onStartScan}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-white font-semibold text-sm transition-all shadow-lg shadow-cyan-500/20">
          🔍 Start Rapid Triage Scan
        </button>
      )}
    </div>
  );
}
