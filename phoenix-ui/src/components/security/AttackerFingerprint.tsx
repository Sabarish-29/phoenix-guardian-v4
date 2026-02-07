/**
 * Attacker Fingerprint Panel.
 *
 * Displays tracked attacker profiles with risk scores,
 * threat type breakdowns, and honeytoken interaction history.
 */

import React, { useEffect, useState } from 'react';
import apiClient from '../../api/client';

interface AttackerProfile {
  attacker_id: string;
  ip_address_anonymized: string;
  first_seen: string;
  last_seen: string;
  attack_count: number;
  threat_types: Record<string, number>;
  sessions: string[];
  honeytokens_triggered: string[];
  risk_score: number;
  status: string;
}

const STATUS_COLORS: Record<string, string> = {
  BLOCKED: 'bg-red-900/40 text-red-400 border-red-700',
  INVESTIGATING: 'bg-yellow-900/40 text-yellow-400 border-yellow-700',
  MONITORING: 'bg-blue-900/40 text-blue-400 border-blue-700',
};

const riskColor = (score: number): string => {
  if (score >= 80) return 'text-red-400';
  if (score >= 50) return 'text-amber-400';
  if (score >= 25) return 'text-yellow-400';
  return 'text-green-400';
};

const riskBarColor = (score: number): string => {
  if (score >= 80) return 'bg-red-500';
  if (score >= 50) return 'bg-amber-500';
  if (score >= 25) return 'bg-yellow-500';
  return 'bg-green-500';
};

export const AttackerFingerprint: React.FC = () => {
  const [attackers, setAttackers] = useState<AttackerProfile[]>([]);
  const [selected, setSelected] = useState<AttackerProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await apiClient.get('/security-console/attackers');
        setAttackers(res.data.attackers || []);
      } catch (err) {
        console.error('Failed to fetch attackers', err);
      } finally {
        setLoading(false);
      }
    };
    fetch();
    const interval = setInterval(fetch, 15000);
    return () => clearInterval(interval);
  }, []);

  const blocked = attackers.filter((a) => a.status === 'BLOCKED').length;

  return (
    <div className="bg-[#1a1f29] border border-[#2d3748] rounded-lg overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#2d3748] flex items-center gap-2">
        <span className="text-lg">🕵️</span>
        <h3 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">Attacker Fingerprints</h3>
        <div className="ml-auto flex gap-3 text-xs">
          <span className="text-gray-400">{attackers.length} profiles</span>
          <span className="text-red-400">{blocked} blocked</span>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden" style={{ maxHeight: 300 }}>
        {/* List */}
        <div className="w-1/2 overflow-y-auto border-r border-[#2d3748]">
          {loading ? (
            <div className="flex items-center justify-center py-10 text-gray-500 text-xs">Loading…</div>
          ) : attackers.length === 0 ? (
            <div className="flex items-center justify-center py-10 text-gray-500 text-xs">No attacker profiles</div>
          ) : (
            attackers.map((a) => (
              <button
                key={a.attacker_id}
                onClick={() => setSelected(a)}
                className={`w-full text-left px-4 py-3 border-b border-[#2d3748]/50 hover:bg-[#232a36] transition-colors ${
                  selected?.attacker_id === a.attacker_id ? 'bg-[#232a36]' : ''
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-300 font-mono">{a.ip_address_anonymized}</span>
                  <span className={`text-xs font-bold ${riskColor(a.risk_score)}`}>{a.risk_score}</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <div className="flex-1 h-1 bg-[#2d3748] rounded-full overflow-hidden">
                    <div className={`h-full ${riskBarColor(a.risk_score)} rounded-full`} style={{ width: `${Math.min(a.risk_score, 100)}%` }} />
                  </div>
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${STATUS_COLORS[a.status] || STATUS_COLORS.MONITORING}`}>
                    {a.status}
                  </span>
                </div>
                <div className="text-[10px] text-gray-500 mt-1">
                  {a.attack_count} attacks · {Object.keys(a.threat_types).length} types · {a.honeytokens_triggered.length} honeytokens
                </div>
              </button>
            ))
          )}
        </div>

        {/* Detail */}
        <div className="w-1/2 overflow-y-auto p-4">
          {selected ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold text-gray-200">{selected.ip_address_anonymized}</h4>
                <span className={`text-lg font-bold ${riskColor(selected.risk_score)}`}>{selected.risk_score}</span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[10px]">
                <div>
                  <span className="text-gray-500">First Seen</span>
                  <p className="text-gray-300">{new Date(selected.first_seen).toLocaleString()}</p>
                </div>
                <div>
                  <span className="text-gray-500">Last Seen</span>
                  <p className="text-gray-300">{new Date(selected.last_seen).toLocaleString()}</p>
                </div>
                <div>
                  <span className="text-gray-500">Total Attacks</span>
                  <p className="text-gray-300 font-bold">{selected.attack_count}</p>
                </div>
                <div>
                  <span className="text-gray-500">Sessions</span>
                  <p className="text-gray-300">{selected.sessions.length}</p>
                </div>
              </div>

              {/* Threat types */}
              <div>
                <span className="text-[10px] text-gray-500 uppercase">Threat Types</span>
                <div className="mt-1 space-y-1">
                  {Object.entries(selected.threat_types).map(([type, count]) => (
                    <div key={type} className="flex items-center justify-between text-[10px]">
                      <span className="text-gray-400 font-mono">{type}</span>
                      <span className="text-gray-300 font-bold">{count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Honeytokens triggered */}
              {selected.honeytokens_triggered.length > 0 && (
                <div>
                  <span className="text-[10px] text-gray-500 uppercase">Honeytokens Triggered</span>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {selected.honeytokens_triggered.map((ht) => (
                      <span key={ht} className="text-[10px] px-2 py-0.5 rounded bg-red-900/30 text-red-400 border border-red-800 font-mono">
                        {ht}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500 text-xs">
              Select an attacker profile to view details
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AttackerFingerprint;
