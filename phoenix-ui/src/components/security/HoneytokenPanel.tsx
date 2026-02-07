/**
 * Honeytoken Panel.
 *
 * Displays the honeytoken registry — synthetic identifiers placed in the system
 * to detect unauthorized data access. Includes legal disclaimer and access log.
 */

import React, { useEffect, useState } from 'react';
import apiClient from '../../api/client';

interface HoneytokenRecord {
  honeytoken_id: string;
  token_type: string;
  value: string;
  status: string;
  access_count: number;
  created_at: string;
  last_accessed?: string;
  triggered_by?: string;
}

const STATUS_BADGE: Record<string, string> = {
  ACTIVE: 'bg-green-900/40 text-green-400 border-green-700',
  TRIGGERED: 'bg-red-900/40 text-red-400 border-red-700',
  EXPIRED: 'bg-gray-800 text-gray-500 border-gray-600',
};

const TYPE_ICONS: Record<string, string> = {
  patient_mrn: '🏥',
  ssn: '🔢',
  email: '📧',
  lab_result: '🧪',
  prescription: '💊',
};

export const HoneytokenPanel: React.FC = () => {
  const [honeytokens, setHoneytokens] = useState<HoneytokenRecord[]>([]);
  const [disclaimer, setDisclaimer] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await apiClient.get('/security-console/honeytokens');
        setHoneytokens(res.data.honeytokens || []);
        setDisclaimer(res.data.disclaimer || '');
      } catch (err) {
        console.error('Failed to fetch honeytokens', err);
      } finally {
        setLoading(false);
      }
    };
    fetch();
    const interval = setInterval(fetch, 30000);
    return () => clearInterval(interval);
  }, []);

  const triggered = honeytokens.filter((h) => h.status === 'TRIGGERED').length;
  const active = honeytokens.filter((h) => h.status === 'ACTIVE').length;

  return (
    <div className="bg-[#1a1f29] border border-[#2d3748] rounded-lg overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#2d3748] flex items-center gap-2">
        <span className="text-lg">🍯</span>
        <h3 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">Honeytoken Registry</h3>
        <div className="ml-auto flex gap-3 text-xs">
          <span className="text-green-400">{active} Active</span>
          <span className="text-red-400">{triggered} Triggered</span>
        </div>
      </div>

      {/* Disclaimer */}
      {disclaimer && (
        <div className="mx-4 mt-3 px-3 py-2 bg-blue-900/20 border border-blue-800/40 rounded text-[10px] text-blue-300 leading-relaxed">
          ⚖️ {disclaimer}
        </div>
      )}

      {/* Table */}
      <div className="overflow-y-auto flex-1 px-1" style={{ maxHeight: 260 }}>
        {loading ? (
          <div className="flex items-center justify-center py-10 text-gray-500 text-xs">Loading…</div>
        ) : (
          <table className="w-full text-xs mt-2">
            <thead className="sticky top-0 bg-[#151a23]">
              <tr className="text-gray-500 uppercase">
                <th className="px-3 py-2 text-left">Type</th>
                <th className="px-3 py-2 text-left">Token ID</th>
                <th className="px-3 py-2 text-left">Value</th>
                <th className="px-3 py-2 text-center">Status</th>
                <th className="px-3 py-2 text-right">Hits</th>
                <th className="px-3 py-2 text-left">Last Accessed</th>
              </tr>
            </thead>
            <tbody>
              {honeytokens.map((h) => (
                <tr key={h.honeytoken_id} className="border-b border-[#2d3748]/50 hover:bg-[#232a36] transition-colors">
                  <td className="px-3 py-2">
                    <span title={h.token_type}>{TYPE_ICONS[h.token_type] || '🔑'}</span>
                    <span className="ml-1 text-gray-400">{h.token_type}</span>
                  </td>
                  <td className="px-3 py-2 text-gray-300 font-mono">{h.honeytoken_id}</td>
                  <td className="px-3 py-2 text-amber-400 font-mono">{h.value}</td>
                  <td className="px-3 py-2 text-center">
                    <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold border ${STATUS_BADGE[h.status] || STATUS_BADGE.ACTIVE}`}>
                      {h.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-gray-300">{h.access_count}</td>
                  <td className="px-3 py-2 text-gray-500 text-[10px]">
                    {h.last_accessed ? new Date(h.last_accessed).toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-[#2d3748] text-[10px] text-gray-500">
        HIPAA §164.312(b) — Access attempts to honeytokens are logged and audited
      </div>
    </div>
  );
};

export default HoneytokenPanel;
