/**
 * Admin Audit Logs Page.
 *
 * Displays a searchable, filterable audit log of system events.
 * In production this would stream from a backend /audit-logs endpoint;
 * here we use realistic mock data.
 */

import React, { useState, useMemo } from 'react';

type Severity = 'INFO' | 'WARNING' | 'CRITICAL' | 'ERROR';
type Category = 'auth' | 'data_access' | 'security' | 'system' | 'clinical';

interface AuditEntry {
  id: number;
  timestamp: string;
  actor: string;
  category: Category;
  action: string;
  resource: string;
  severity: Severity;
  ip: string;
}

const NOW = new Date();
const ts = (minsAgo: number) => new Date(NOW.getTime() - minsAgo * 60000).toISOString();

const MOCK_ENTRIES: AuditEntry[] = [
  { id: 1,  timestamp: ts(2),   actor: 'admin@phoenixguardian.health',     category: 'auth',        action: 'LOGIN_SUCCESS',            resource: '/auth/login',                    severity: 'INFO',     ip: '10.0.0.1' },
  { id: 2,  timestamp: ts(5),   actor: 'system',                           category: 'security',    action: 'THREAT_BLOCKED',            resource: 'sentinel/prompt-injection',       severity: 'CRITICAL', ip: '203.0.113.42' },
  { id: 3,  timestamp: ts(12),  actor: 'dr.smith@phoenixguardian.health',  category: 'clinical',    action: 'ENCOUNTER_CREATED',         resource: '/encounters/new',                 severity: 'INFO',     ip: '10.0.0.5' },
  { id: 4,  timestamp: ts(18),  actor: 'system',                           category: 'system',      action: 'HEALTH_CHECK',              resource: '/health',                        severity: 'INFO',     ip: '127.0.0.1' },
  { id: 5,  timestamp: ts(25),  actor: 'nurse.jones@phoenixguardian.health', category: 'data_access', action: 'PATIENT_RECORD_VIEW',     resource: '/patients/P-1042',                severity: 'INFO',     ip: '10.0.0.8' },
  { id: 6,  timestamp: ts(30),  actor: 'system',                           category: 'security',    action: 'HONEYTOKEN_TRIGGERED',      resource: 'honeytoken/fake-ssn-field',       severity: 'WARNING',  ip: '198.51.100.7' },
  { id: 7,  timestamp: ts(45),  actor: 'admin@phoenixguardian.health',     category: 'security',    action: 'SECURITY_REPORT_GENERATED', resource: '/admin/reports',                  severity: 'INFO',     ip: '10.0.0.1' },
  { id: 8,  timestamp: ts(60),  actor: 'system',                           category: 'system',      action: 'PQC_KEY_ROTATION',          resource: 'crypto/ml-kem-768',              severity: 'INFO',     ip: '127.0.0.1' },
  { id: 9,  timestamp: ts(75),  actor: 'unknown',                          category: 'auth',        action: 'LOGIN_FAILED',              resource: '/auth/login',                    severity: 'WARNING',  ip: '203.0.113.99' },
  { id: 10, timestamp: ts(90),  actor: 'system',                           category: 'security',    action: 'RATE_LIMIT_EXCEEDED',       resource: '/api/v1/encounters',             severity: 'WARNING',  ip: '192.0.2.55' },
  { id: 11, timestamp: ts(120), actor: 'dr.smith@phoenixguardian.health',  category: 'clinical',    action: 'SOAP_GENERATED',            resource: '/encounters/ENC-2045/soap',       severity: 'INFO',     ip: '10.0.0.5' },
  { id: 12, timestamp: ts(180), actor: 'system',                           category: 'security',    action: 'THREAT_DETECTED',           resource: 'sentinel/data-exfiltration',      severity: 'CRITICAL', ip: '203.0.113.42' },
];

const SEV_STYLE: Record<Severity, string> = {
  INFO:     'bg-blue-100 text-blue-700',
  WARNING:  'bg-yellow-100 text-yellow-700',
  ERROR:    'bg-orange-100 text-orange-700',
  CRITICAL: 'bg-red-100 text-red-700',
};

const CAT_STYLE: Record<Category, string> = {
  auth:        'bg-indigo-100 text-indigo-700',
  data_access: 'bg-teal-100 text-teal-700',
  security:    'bg-red-50 text-red-600',
  system:      'bg-gray-100 text-gray-600',
  clinical:    'bg-green-100 text-green-700',
};

const CATEGORIES: Category[] = ['auth', 'data_access', 'security', 'system', 'clinical'];
const SEVERITIES: Severity[] = ['INFO', 'WARNING', 'ERROR', 'CRITICAL'];

export const AdminAuditLogsPage: React.FC = () => {
  const [search, setSearch] = useState('');
  const [filterCat, setFilterCat] = useState<Category | ''>('');
  const [filterSev, setFilterSev] = useState<Severity | ''>('');

  const filtered = useMemo(() => {
    let rows = MOCK_ENTRIES;
    if (filterCat) rows = rows.filter((e) => e.category === filterCat);
    if (filterSev) rows = rows.filter((e) => e.severity === filterSev);
    if (search) {
      const q = search.toLowerCase();
      rows = rows.filter(
        (e) =>
          e.actor.toLowerCase().includes(q) ||
          e.action.toLowerCase().includes(q) ||
          e.resource.toLowerCase().includes(q) ||
          e.ip.includes(q)
      );
    }
    return rows;
  }, [search, filterCat, filterSev]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">📋 Audit Logs</h1>
        <p className="text-gray-500 mt-1 text-sm">HIPAA-compliant activity log — all access and security events</p>
      </div>

      {/* Filters */}
      <div className="card flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder="Search actor, action, resource, IP…"
          className="flex-1 min-w-[200px] border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
          value={filterCat}
          onChange={(e) => setFilterCat(e.target.value as Category | '')}
        >
          <option value="">All Categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c.replace('_', ' ')}</option>
          ))}
        </select>
        <select
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
          value={filterSev}
          onChange={(e) => setFilterSev(e.target.value as Severity | '')}
        >
          <option value="">All Severities</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <span className="text-xs text-gray-400">{filtered.length} / {MOCK_ENTRIES.length} entries</span>
      </div>

      {/* Log Table */}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500 text-xs uppercase">
              <th className="pb-2 pr-3">Time</th>
              <th className="pb-2 pr-3">Actor</th>
              <th className="pb-2 pr-3">Category</th>
              <th className="pb-2 pr-3">Action</th>
              <th className="pb-2 pr-3">Resource</th>
              <th className="pb-2 pr-3">Severity</th>
              <th className="pb-2">Source IP</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((e) => (
              <tr key={e.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-2.5 pr-3 text-gray-500 text-xs whitespace-nowrap font-mono">
                  {new Date(e.timestamp).toLocaleTimeString()}
                </td>
                <td className="py-2.5 pr-3 text-gray-700 text-xs font-mono truncate max-w-[180px]" title={e.actor}>{e.actor}</td>
                <td className="py-2.5 pr-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${CAT_STYLE[e.category]}`}>
                    {e.category.replace('_', ' ')}
                  </span>
                </td>
                <td className="py-2.5 pr-3 text-gray-800 text-xs font-medium">{e.action}</td>
                <td className="py-2.5 pr-3 text-gray-500 text-xs font-mono truncate max-w-[220px]" title={e.resource}>{e.resource}</td>
                <td className="py-2.5 pr-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${SEV_STYLE[e.severity]}`}>
                    {e.severity}
                  </span>
                </td>
                <td className="py-2.5 text-gray-500 text-xs font-mono">{e.ip}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="py-8 text-center text-gray-400 text-sm">No matching audit log entries</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Compliance */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-3">
        <span className="text-xl mt-0.5">⚖️</span>
        <div>
          <h3 className="font-semibold text-amber-900 text-sm">Audit Retention Policy</h3>
          <p className="text-xs text-amber-800 mt-1 leading-relaxed">
            Audit logs are retained for a minimum of 6 years per HIPAA §164.530(j).
            Logs are stored in immutable, tamper-evident storage with cryptographic hashing.
            Access to audit logs is restricted to admin and auditor roles.
          </p>
        </div>
      </div>
    </div>
  );
};

export default AdminAuditLogsPage;
