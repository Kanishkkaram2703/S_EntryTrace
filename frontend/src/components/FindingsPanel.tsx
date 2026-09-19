import type { FindingSummary } from '../api/client';

interface Props {
  findings: FindingSummary | null;
  scanId: string | undefined;
}

const severityColors: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400',
  high: 'bg-orange-500/15 text-orange-400',
  medium: 'bg-amber-500/15 text-amber-400',
  low: 'bg-cyan-500/15 text-cyan-400',
  info: 'bg-gray-500/15 text-gray-400',
  unknown: 'bg-gray-500/15 text-gray-400',
};

export function FindingsPanel({ findings, scanId }: Props) {
  if (!scanId) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold">Findings</h2>
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-8 text-center">
          <p className="text-3xl mb-3">🔎</p>
          <p className="text-[var(--text-secondary)]">No scan results available</p>
          <p className="text-xs text-[var(--text-muted)] mt-2">Complete a scan to view findings.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Findings</h2>
        <p className="text-xs text-[var(--text-muted)]">Scan: {scanId}</p>
      </div>

      {!findings ? (
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6 text-center">
          <p className="text-[var(--text-secondary)]">Loading findings...</p>
        </div>
      ) : findings.total === 0 ? (
        <div className="space-y-4">
          <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-6 text-center">
            <p className="text-3xl mb-3">✅</p>
            <p className="text-lg text-[var(--text-secondary)]">No findings detected by MVT analysis</p>
            <p className="text-xs text-[var(--text-muted)] mt-3 max-w-lg mx-auto">
              This does NOT guarantee the device is safe. MVT analysis is limited to supported artifacts and publicly available indicators of compromise. Absence of findings may mean the threat is not covered by current IOC databases.
            </p>
          </div>
          <div className="bg-amber-900/20 border border-amber-800 rounded-lg p-4 text-xs text-amber-300">
            ⚠ No IOC feed was configured for this scan. IOC matching is only available when STIX2 indicator files are provided.
          </div>
        </div>
      ) : (
        <>
          {/* Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-4 text-center">
              <p className="text-2xl font-bold">{findings.total}</p>
              <p className="text-xs text-[var(--text-muted)]">Total</p>
            </div>
            {Object.entries(findings.by_severity).map(([sev, count]) => (
              <div key={sev} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-4 text-center">
                <p className="text-2xl font-bold">{count}</p>
                <p className="text-xs text-[var(--text-muted)] capitalize">{sev}</p>
              </div>
            ))}
          </div>

          {/* Individual findings */}
          <div className="space-y-3">
            {findings.findings.map(f => (
              <div key={f.finding_id} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${severityColors[f.severity] || severityColors.unknown}`}>
                        {f.severity}
                      </span>
                      <span className="text-xs text-[var(--text-muted)]">{f.category}</span>
                    </div>
                    <p className="text-sm font-medium">{f.title}</p>
                    {f.description && <p className="text-xs text-[var(--text-secondary)] mt-1">{f.description}</p>}
                    <p className="text-xs text-[var(--text-muted)] mt-1">Module: {f.source_module} · Confidence: {f.confidence}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
