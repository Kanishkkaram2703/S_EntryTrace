/**
 * S*EntryTrace — API Client
 * Typed interface to the FastAPI backend.
 */

const BASE = '/api';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

// ── Types ─────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  mvt: { available: boolean; version: string | null; module_count: number };
  adb: { available: boolean; version: string | null; adb_path: string | null };
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
  last_verified_at: string | null;
  metadata_state: string;
}

export interface DeviceListResponse {
  count: number;
  devices: DeviceInfo[];
}

export interface ScanStage {
  stage_id: string;
  display_name: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  summary: string;
  error: string | null;
  records_processed: number;
}

export interface TimelineEntry {
  time: string;
  timestamp: string;
  level: 'INFO' | 'SUCCESS' | 'WARN' | 'ERROR';
  message: string;
}

export interface ScanState {
  scan_id: string;
  device_serial: string;
  device: Record<string, unknown>;
  scan_profile: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  mvt_version: string | null;
  adb_version: string | null;
  current_operation: string;
  log: string;
  timeline: TimelineEntry[];
  warnings: string[];
  errors: string[];
  findings_count: number;
  stages: ScanStage[];
}

export interface ScanListItem {
  scan_id: string;
  status: string;
  device_serial: string;
  device_model: string | null;
  device_manufacturer: string | null;
  started_at: string | null;
  completed_at: string | null;
  findings_count: number;
  has_manifest: boolean;
  has_report: boolean;
}

export interface Finding {
  finding_id: string;
  scan_id: string;
  category: string;
  title: string;
  description: string;
  severity: string;
  confidence: string;
  source_module: string;
  evidence_path: string | null;
  mvt_level: string | null;
  mvt_message: string | null;
  event_time: string | null;
  event_data: Record<string, unknown> | null;
  explanation: string;
  why_it_matters: string;
  interpretation: string;
}

export interface AnalysisModule {
  module_name: string;
  display_name: string;
  records_processed: number;
  alerts_generated: number;
  status: string;
  summary: string;
}

export interface FindingSummary {
  scan_id: string;
  total: number;
  by_category: Record<string, number>;
  by_severity: Record<string, number>;
  findings: Finding[];
  modules_analyzed: AnalysisModule[];
  ioc_configured: boolean;
  ioc_indicators_loaded: number;
  total_records_processed: number;
}

export interface EvidenceFile {
  relative_path: string;
  size_bytes: number;
  sha256: string;
}

export interface Manifest {
  scan_id: string;
  file_count: number;
  total_bytes: number;
  files: EvidenceFile[];
  collection_status: string;
  mvt_version: string;
  adb_version: string;
  scan_profile: string;
  collection_start: string;
  collection_end: string;
  generated_at: string;
  warnings: string[];
  errors: string[];
  limitations: string[];
}

// ── API ───────────────────────────────────────────────

export const api = {
  health: () => get<HealthResponse>('/health'),
  listDevices: () => get<DeviceListResponse>('/devices'),
  getDevice: (serial: string) => get<DeviceInfo>(`/devices/${serial}`),
  startScan: (serial: string) => post<{ scan_id: string; status: string }>('/scans', { device_serial: serial }),
  listScans: () => get<{ count: number; scans: ScanListItem[] }>('/scans'),
  getScan: (id: string) => get<ScanState>(`/scans/${id}`),
  getScanLogs: (id: string) => get<{ logs: string }>(`/scans/${id}/logs`),
  getTimeline: (id: string) => get<{ scan_id: string; timeline: TimelineEntry[] }>(`/scans/${id}/timeline`),
  getManifest: (id: string) => get<Manifest>(`/scans/${id}/manifest`),
  getFindings: (id: string) => get<FindingSummary>(`/scans/${id}/findings`),
  cancelScan: (id: string) => post<{ message: string }>(`/scans/${id}/cancel`),
  getReportUrl: (id: string) => `${BASE}/reports/${id}`,
  getReportPdfUrl: (id: string) => `${BASE}/reports/${id}/pdf`,
  getReportStatus: (id: string) => get<{ scan_id: string; exists: boolean; status: string; size_bytes: number }>(`/reports/${id}/status`),
  generateReport: (id: string) => post<{ scan_id: string; status: string; size_bytes: number }>(`/reports/${id}/generate`),
};
