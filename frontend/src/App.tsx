import { useState, useEffect } from 'react';
import './index.css';
import { api, HealthData, DeviceInfo, ScanInfo, FindingSummary } from './api/client';
import { Dashboard } from './components/Dashboard';
import { DevicePanel } from './components/DevicePanel';
import { ScanPanel } from './components/ScanPanel';
import { FindingsPanel } from './components/FindingsPanel';
import { EvidencePanel } from './components/EvidencePanel';

type Tab = 'dashboard' | 'device' | 'scan' | 'findings' | 'evidence';

export default function App() {
  const [tab, setTab] = useState<Tab>('dashboard');
  const [health, setHealth] = useState<HealthData | null>(null);
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<DeviceInfo | null>(null);
  const [activeScan, setActiveScan] = useState<ScanInfo | null>(null);
  const [findings, setFindings] = useState<FindingSummary | null>(null);
  const [manifest, setManifest] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Initial health + device load
  useEffect(() => {
    loadHealth();
    loadDevices();
    const iv = setInterval(loadDevices, 10000);
    return () => clearInterval(iv);
  }, []);

  // Poll scan status when scan is running
  useEffect(() => {
    if (!activeScan || activeScan.status === 'completed' || activeScan.status === 'failed' || activeScan.status === 'cancelled') return;
    const iv = setInterval(async () => {
      try {
        const scan = await api.getScan(activeScan.scan_id);
        setActiveScan(scan);
        if (scan.status === 'completed' || scan.status === 'failed') {
          loadFindings(scan.scan_id);
          loadManifest(scan.scan_id);
        }
      } catch { /* ignore poll errors */ }
    }, 3000);
    return () => clearInterval(iv);
  }, [activeScan?.scan_id, activeScan?.status]);

  async function loadHealth() {
    try {
      const h = await api.health();
      setHealth(h);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadDevices() {
    try {
      const d = await api.listDevices();
      setDevices(d.devices);
      if (d.devices.length === 1 && d.devices[0].state === 'connected') {
        setSelectedDevice(d.devices[0]);
      }
    } catch { /* silent device poll failure */ }
  }

  async function selectDevice(d: DeviceInfo) {
    try {
      const detailed = await api.getDevice(d.serial);
      setSelectedDevice(detailed);
      setTab('device');
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function startScan() {
    if (!selectedDevice) return;
    try {
      setError(null);
      const result = await api.startScan(selectedDevice.serial);
      setActiveScan({ scan_id: result.scan_id, status: result.status, device_serial: selectedDevice.serial });
      setTab('scan');
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function loadFindings(scanId: string) {
    try {
      const f = await api.getScanFindings(scanId);
      setFindings(f);
    } catch { /* ignore */ }
  }

  async function loadManifest(scanId: string) {
    try {
      const m = await api.getScanManifest(scanId);
      setManifest(m);
    } catch { /* ignore */ }
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'dashboard', label: 'Dashboard' },
    { key: 'device', label: 'Device' },
    { key: 'scan', label: 'Scan' },
    { key: 'findings', label: 'Findings' },
    { key: 'evidence', label: 'Evidence' },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-[var(--bg-secondary)] border-b border-[var(--border-color)] px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center text-white font-bold text-lg">S</div>
            <div>
              <h1 className="text-xl font-bold text-[var(--text-primary)]">S*EntryTrace</h1>
              <p className="text-xs text-[var(--text-muted)]">Android Digital Forensics Workstation</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {health && (
              <div className="flex items-center gap-2 text-xs">
                <span className={`w-2 h-2 rounded-full ${health.status === 'ok' ? 'bg-emerald-400' : 'bg-red-400'}`}></span>
                <span className="text-[var(--text-secondary)]">v{health.app_version}</span>
              </div>
            )}
          </div>
        </div>
        {/* Nav */}
        <nav className="flex gap-1 mt-4">
          {tabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${tab === t.key
                ? 'bg-cyan-500/15 text-cyan-400'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/5'}`}>
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Error banner */}
      {error && (
        <div className="bg-red-900/40 border-b border-red-700 px-6 py-3 text-sm text-red-300 flex items-center justify-between">
          <span>⚠ {error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-white text-xs">Dismiss</button>
        </div>
      )}

      {/* Content */}
      <main className="flex-1 p-6">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-[var(--text-muted)]">Connecting to backend...</div>
          </div>
        ) : (
          <>
            {tab === 'dashboard' && <Dashboard health={health} devices={devices} activeScan={activeScan} onSelectDevice={selectDevice} />}
            {tab === 'device' && <DevicePanel device={selectedDevice} devices={devices} onSelect={selectDevice} onStartScan={startScan} />}
            {tab === 'scan' && <ScanPanel scan={activeScan} onStart={startScan} selectedDevice={selectedDevice} />}
            {tab === 'findings' && <FindingsPanel findings={findings} scanId={activeScan?.scan_id} />}
            {tab === 'evidence' && <EvidencePanel manifest={manifest} scanId={activeScan?.scan_id} />}
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-[var(--bg-secondary)] border-t border-[var(--border-color)] px-6 py-3 text-center text-xs text-[var(--text-muted)]">
        S*EntryTrace — Master's Project • MVT {health?.mvt?.version || '?'} • ADB {health?.adb?.version || '?'}
      </footer>
    </div>
  );
}
