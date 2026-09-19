import type { HealthData, DeviceInfo, ScanInfo } from '../api/client';

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${ok ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-emerald-400' : 'bg-red-400'}`}></span>
      {label}
    </span>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-5 hover:border-cyan-800/40 transition-colors">
      <h3 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">{title}</h3>
      {children}
    </div>
  );
}

interface Props {
  health: HealthData | null;
  devices: DeviceInfo[];
  activeScan: ScanInfo | null;
  onSelectDevice: (d: DeviceInfo) => void;
}

export function Dashboard({ health, devices, activeScan, onSelectDevice }: Props) {
  if (!health) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <p className="text-2xl mb-2">⚠️</p>
          <p className="text-[var(--text-secondary)]">Backend unavailable</p>
          <p className="text-xs text-[var(--text-muted)] mt-1">Ensure the backend server is running on port 8000</p>
        </div>
      </div>
    );
  }

  const connectedDevices = devices.filter(d => d.state === 'connected');

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-1">Dashboard</h2>
        <p className="text-[var(--text-muted)] text-sm">System status overview</p>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card title="Backend">
          <div className="space-y-2">
            <StatusBadge ok={health.status === 'ok'} label={health.status === 'ok' ? 'Online' : 'Error'} />
            <p className="text-xs text-[var(--text-muted)]">v{health.app_version} · {health.environment}</p>
          </div>
        </Card>

        <Card title="MVT Engine">
          <div className="space-y-2">
            <StatusBadge ok={health.mvt.available} label={health.mvt.available ? 'Available' : 'Unavailable'} />
            <p className="text-xs text-[var(--text-muted)]">
              {health.mvt.version ? `v${health.mvt.version}` : 'Not detected'} · {health.mvt.module_count} modules
            </p>
          </div>
        </Card>

        <Card title="ADB">
          <div className="space-y-2">
            <StatusBadge ok={health.adb.available} label={health.adb.available ? 'Available' : 'Not Found'} />
            <p className="text-xs text-[var(--text-muted)]">
              {health.adb.version ? `v${health.adb.version}` : 'Not detected'}
            </p>
          </div>
        </Card>

        <Card title="Devices">
          <div className="space-y-2">
            <StatusBadge ok={connectedDevices.length > 0} label={connectedDevices.length > 0 ? `${connectedDevices.length} Connected` : 'No Device'} />
            <p className="text-xs text-[var(--text-muted)]">
              {devices.length} visible · {connectedDevices.length} authorized
            </p>
          </div>
        </Card>
      </div>

      {/* Active Scan */}
      {activeScan && (
        <Card title="Last Scan">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                activeScan.status === 'completed' ? 'bg-emerald-500/15 text-emerald-400' :
                activeScan.status === 'running' ? 'bg-cyan-500/15 text-cyan-400' :
                activeScan.status === 'failed' ? 'bg-red-500/15 text-red-400' :
                'bg-gray-500/15 text-gray-400'
              }`}>{activeScan.status}</span>
              <span className="text-xs text-[var(--text-muted)]">{activeScan.scan_id}</span>
            </div>
            {activeScan.current_operation && (
              <p className="text-xs text-[var(--text-secondary)]">{activeScan.current_operation}</p>
            )}
          </div>
        </Card>
      )}

      {/* Device list */}
      {devices.length > 0 ? (
        <Card title="Detected Devices">
          <div className="space-y-2">
            {devices.map(d => (
              <button key={d.serial} onClick={() => onSelectDevice(d)}
                className="w-full flex items-center justify-between p-3 rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--bg-card-hover)] transition-colors text-left">
                <div>
                  <p className="text-sm font-medium">{d.model || d.serial}</p>
                  <p className="text-xs text-[var(--text-muted)]">{d.serial}</p>
                </div>
                <span className={`px-2 py-0.5 rounded text-xs ${
                  d.state === 'connected' ? 'bg-emerald-500/15 text-emerald-400' :
                  d.state === 'unauthorized' ? 'bg-amber-500/15 text-amber-400' :
                  'bg-red-500/15 text-red-400'
                }`}>{d.state}</span>
              </button>
            ))}
          </div>
        </Card>
      ) : (
        <Card title="No Device Connected">
          <div className="text-center py-6">
            <p className="text-3xl mb-3">📱</p>
            <p className="text-[var(--text-secondary)]">No Android device detected</p>
            <p className="text-xs text-[var(--text-muted)] mt-2 max-w-md mx-auto">
              Connect an Android device via USB, enable USB Debugging in Developer Options, and authorize the connection when prompted.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}
