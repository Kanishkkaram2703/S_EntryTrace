/**
 * S*EntryTrace — API Client
 * Connects frontend to the FastAPI backend.
 * Never fabricates responses — reports actual errors.
 */

const BASE = '';  // Proxied through Vite dev server

export interface HealthData {
  app_name: string;
  app_version: string;
  environment: string;
  status: string;
  mvt: { available: boolean; version: string | null; module_count: number };
  adb: { available: boolean; version: string | null };
}

export interface DeviceInfo {
  serial: string;
  model: string | null;
  manufacturer: string | null;
  android_version: string | null;
  sdk_level: string | null;
  security_patch: string | null;
  build_fingerprint: string | null;
  state: string;
  is_rooted: boolean | null;
  adb_version: string | null;
  detected_at: string;
}

export interface ScanInfo {
  scan_id: string;
  status: string;
  device_serial: string;
  current_operation?: string;
  started_at?: string;
  completed_at?: string;
  warnings?: string[];
  errors?: string[];
  findings_count?: number;
}

export interface FindingSummary {
  scan_id: string;
  total: number;
  by_category: Record<string, number>;
  by_severity: Record<string, number>;
  findings: Array<{
    finding_id: string;
    category: string;
    title: string;
    description: string;
    severity: string;
    confidence: string;
    source_module: string;
  }>;
}

async function apiFetch<T>(url: string, opts?: RequestInit): Promise<T> {
  try {
    const res = await fetch(`${BASE}${url}`, opts);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || err.error || `HTTP ${res.status}`);
    }
    return res.json();
  } catch (e: any) {
    if (e.message?.includes('Failed to fetch') || e.message?.includes('NetworkError')) {
      throw new Error('Backend unavailable. Ensure the backend server is running on port 8000.');
    }
    throw e;
  }
}

export const api = {
  health: () => apiFetch<HealthData>('/health'),
  engineStatus: () => apiFetch<any>('/api/engine/status'),
  listDevices: () => apiFetch<{ count: number; devices: DeviceInfo[] }>('/api/devices'),
  getDevice: (serial: string) => apiFetch<DeviceInfo>(`/api/devices/${encodeURIComponent(serial)}`),
  startScan: (serial: string) =>
    apiFetch<{ scan_id: string; status: string }>('/api/scans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_serial: serial, scan_profile: 'rapid_triage' }),
    }),
  listScans: () => apiFetch<{ count: number; scans: ScanInfo[] }>('/api/scans'),
  getScan: (id: string) => apiFetch<ScanInfo>(`/api/scans/${id}`),
  getScanLogs: (id: string) => apiFetch<{ scan_id: string; logs: string }>(`/api/scans/${id}/logs`),
  getScanFindings: (id: string) => apiFetch<FindingSummary>(`/api/scans/${id}/findings`),
  getScanManifest: (id: string) => apiFetch<any>(`/api/scans/${id}/manifest`),
  cancelScan: (id: string) =>
    apiFetch<any>(`/api/scans/${id}/cancel`, { method: 'POST' }),
  getReportUrl: (id: string) => `${BASE}/api/reports/${id}`,
};
