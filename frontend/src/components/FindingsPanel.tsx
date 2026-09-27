import { useState } from 'react';
import { FileSearch, ChevronDown, ChevronRight, Shield, Info, AlertTriangle, Database } from 'lucide-react';
import type { FindingSummary, Finding, ScanState } from '../api/client';

interface Props {
  findings: FindingSummary | null;
  scanId: string | undefined;
  scanState: ScanState | null;
}

function SeverityBadge({ severity }: { severity: string }) {
  const cls = `badge severity-${severity}`;
  return <span className={cls}>{severity}</span>;
}

function FindingCard({ finding }: { finding: Finding }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="finding-card">
      <div className="finding-header" onClick={() => setExpanded(!expanded)} style={{ cursor: 'pointer' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <span className="finding-title">{finding.title}</span>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
          <SeverityBadge severity={finding.severity} />
          <span className="badge badge-neutral" style={{ textTransform: 'none' }}>{finding.category}</span>
        </div>
      </div>

      {expanded && (
        <div style={{ paddingLeft: 22 }}>
          {finding.explanation && (
            <div className="finding-detail">
              <strong>What was observed:</strong> {finding.explanation}
            </div>
          )}
          {finding.why_it_matters && (
            <div className="finding-detail">
              <strong>Why it matters:</strong> {finding.why_it_matters}
            </div>
          )}
          {finding.interpretation && (
            <div className="finding-detail">
              <strong>Interpretation:</strong> {finding.interpretation}
            </div>
          )}
          {finding.event_time && (
            <div className="finding-detail">
              <strong>Event time:</strong> {finding.event_time}
            </div>
          )}
          <div className="finding-detail" style={{ marginTop: 8 }}>
            <span className="text-xs text-muted">Source: {finding.source_module} · MVT Level: {finding.mvt_level || 'N/A'}</span>
          </div>

          {/* Technical Details */}
          {finding.event_data && (
            <details style={{ marginTop: 8 }}>
              <summary className="text-xs text-muted" style={{ cursor: 'pointer' }}>Raw event data</summary>
              <div className="log-viewer" style={{ maxHeight: 200, marginTop: 4, fontSize: '0.625rem' }}>
                {JSON.stringify(finding.event_data, null, 2)}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

export function FindingsPanel({ findings, scanId, scanState }: Props) {
  if (!scanId) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <h1>Findings</h1>
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: 48 }}>
            <FileSearch size={40} color="var(--color-text-muted)" style={{ marginBottom: 12 }} />
            <p style={{ fontWeight: 500 }}>No Examination Selected</p>
            <p className="text-sm text-muted" style={{ marginTop: 8 }}>
              Select an examination from the History tab to view its findings.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!findings) {
    const isFailed = scanState?.status === 'failed';
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <h1>Findings</h1>
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: 48 }}>
            <FileSearch size={40} color="var(--color-text-muted)" style={{ marginBottom: 12 }} />
            <p style={{ fontWeight: 500 }}>{isFailed ? 'Findings Not Assessed' : 'No Findings Available'}</p>
            <p className="text-sm text-muted" style={{ marginTop: 8 }}>
              {isFailed
                ? 'The examination could not complete successfully. Findings were not fully assessed.'
                : 'Complete an examination to view findings.'}
            </p>
          </div>
        </div>
      </div>
    );
  }


  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1>Examination Findings</h1>
        <p className="text-sm text-muted" style={{ marginTop: 4 }}>
          Analysis results for {scanId}
        </p>
      </div>

      {/* Analysis Summary */}
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-icon" style={{ background: findings.total > 0 ? 'var(--color-warning-bg)' : 'var(--color-success-bg)', color: findings.total > 0 ? 'var(--color-warning)' : 'var(--color-success)' }}>
            <AlertTriangle />
          </div>
          <div>
            <div className="stat-value">{findings.total}</div>
            <div className="stat-label">Observations</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'var(--color-info-bg)', color: 'var(--color-info)' }}>
            <Database />
          </div>
          <div>
            <div className="stat-value">{findings.total_records_processed.toLocaleString()}</div>
            <div className="stat-label">Records Analyzed</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: '#f3f4f6', color: '#6b7280' }}>
            <FileSearch />
          </div>
          <div>
            <div className="stat-value">{findings.modules_analyzed.length}</div>
            <div className="stat-label">Modules Ran</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ background: findings.ioc_configured ? 'var(--color-success-bg)' : '#f3f4f6', color: findings.ioc_configured ? 'var(--color-success)' : '#9ca3af' }}>
            <Shield />
          </div>
          <div>
            <div className="stat-value">{findings.ioc_configured ? `${findings.ioc_indicators_loaded}` : 'None'}</div>
            <div className="stat-label">IOC Indicators</div>
          </div>
        </div>
      </div>

      {/* IOC notice */}
      {!findings.ioc_configured && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: 'var(--color-info-bg)', borderRadius: 'var(--radius)', fontSize: '0.8125rem', color: 'var(--color-info)' }}>
          <Info size={14} style={{ flexShrink: 0 }} />
          <span>No threat indicator database was configured. The analysis checked for suspicious patterns only. For targeted threat detection, configure STIX2 indicators.</span>
        </div>
      )}

      {/* Severity breakdown */}
      {findings.total > 0 && Object.keys(findings.by_severity).length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">Severity Breakdown</div>
          </div>
          <div className="card-body" style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {Object.entries(findings.by_severity).map(([sev, count]) => (
              <div key={sev} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <SeverityBadge severity={sev} />
                <span className="text-sm">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Finding list */}
      {findings.findings.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><AlertTriangle size={18} /> Observations ({findings.findings.length})</div>
          </div>
          <div className="card-body" style={{ padding: '12px 16px' }}>
            {findings.findings.map(f => (
              <FindingCard key={f.finding_id} finding={f} />
            ))}
          </div>
        </div>
      )}

      {findings.total === 0 && (
        <div className="card">
          <div className="card-body" style={{ padding: 24 }}>
            <p style={{ fontWeight: 500 }}>No observations were flagged by the analysis.</p>
            <p className="text-sm text-muted" style={{ marginTop: 8 }}>
              This does <strong>not</strong> guarantee the device is free of threats. The analysis is limited to the artifacts and indicators supported by MVT.
            </p>
          </div>
        </div>
      )}

      {/* Modules Analyzed */}
      {findings.modules_analyzed.length > 0 && (
        <details className="card">
          <summary className="expandable-header" style={{ listStyle: 'none' }}>
            <span className="card-title" style={{ fontSize: '0.875rem' }}>What Was Analyzed ({findings.modules_analyzed.length} modules)</span>
            <span className="text-xs text-muted">Click to expand</span>
          </summary>
          <div className="expandable-content">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {findings.modules_analyzed.map(m => (
                <div key={m.module_name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--color-border-light)' }}>
                  <span className="text-sm">{m.display_name}</span>
                  <span className="text-xs text-muted">{m.records_processed.toLocaleString()} records{m.alerts_generated > 0 ? ` · ${m.alerts_generated} alerts` : ''}</span>
                </div>
              ))}
            </div>
          </div>
        </details>
      )}
    </div>
  );
}
