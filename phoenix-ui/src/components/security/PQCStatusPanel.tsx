/**
 * PQC Status Panel.
 *
 * Displays post-quantum cryptography status including:
 * - Kyber-1024 algorithm status
 * - PHI field encryption coverage
 * - Key rotation status
 * - Encryption/decryption performance
 */

import React, { useEffect, useState } from 'react';
import apiClient from '../../api/client';

interface PQCStatus {
  algorithm: string;
  nist_status: string;
  quantum_resistance_bits: number;
  status: string;
  encrypted_fields_count: number;
  total_phi_fields: number;
  phi_fields: string[];
  last_key_rotation: string;
  avg_encrypt_time_ms: number;
  avg_decrypt_time_ms: number;
  total_operations: number;
  compliance: string;
}

export const PQCStatusPanel: React.FC = () => {
  const [pqc, setPqc] = useState<PQCStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await apiClient.get('/security-console/pqc-status');
        setPqc(res.data);
      } catch (err) {
        console.error('Failed to fetch PQC status', err);
      } finally {
        setLoading(false);
      }
    };
    fetch();
    const interval = setInterval(fetch, 60000);
    return () => clearInterval(interval);
  }, []);

  const coveragePercent = pqc ? Math.round((pqc.encrypted_fields_count / pqc.total_phi_fields) * 100) : 0;

  return (
    <div className="bg-[#1a1f29] border border-[#2d3748] rounded-lg overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#2d3748] flex items-center gap-2">
        <span className="text-lg">🔐</span>
        <h3 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">Post-Quantum Crypto</h3>
        {pqc && (
          <span className={`ml-auto inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border ${
            pqc.status === 'ACTIVE' ? 'bg-green-900/40 text-green-400 border-green-700' : 'bg-red-900/40 text-red-400 border-red-700'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${pqc.status === 'ACTIVE' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
            {pqc.status}
          </span>
        )}
      </div>

      <div className="flex-1 p-4 overflow-y-auto" style={{ maxHeight: 340 }}>
        {loading ? (
          <div className="flex items-center justify-center h-full text-gray-500 text-xs">Loading…</div>
        ) : pqc ? (
          <div className="space-y-4">
            {/* Algorithm info */}
            <div className="bg-[#151a23] rounded-lg p-3 border border-[#2d3748]">
              <div className="text-[10px] text-gray-500 uppercase mb-1">Algorithm</div>
              <div className="text-sm text-cyan-400 font-mono font-bold">{pqc.algorithm}</div>
              <div className="text-[10px] text-gray-400 mt-1">{pqc.nist_status}</div>
              <div className="text-[10px] text-gray-500 mt-0.5">{pqc.quantum_resistance_bits}-bit quantum resistance</div>
            </div>

            {/* Coverage */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="text-[10px] text-gray-500 uppercase">PHI Field Coverage</span>
                <span className="text-xs text-green-400 font-bold">{coveragePercent}%</span>
              </div>
              <div className="h-2 bg-[#2d3748] rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 to-green-500 rounded-full transition-all"
                  style={{ width: `${coveragePercent}%` }}
                />
              </div>
              <div className="text-[10px] text-gray-500 mt-1">
                {pqc.encrypted_fields_count}/{pqc.total_phi_fields} PHI fields encrypted
              </div>
            </div>

            {/* PHI Fields grid */}
            <div>
              <div className="text-[10px] text-gray-500 uppercase mb-1">Encrypted PHI Fields</div>
              <div className="flex flex-wrap gap-1">
                {pqc.phi_fields.map((field) => (
                  <span
                    key={field}
                    className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-900/30 text-cyan-400 border border-cyan-800/50 font-mono"
                  >
                    ✓ {field}
                  </span>
                ))}
              </div>
            </div>

            {/* Performance metrics */}
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-[#151a23] rounded p-2 text-center border border-[#2d3748]">
                <div className="text-[10px] text-gray-500">Encrypt</div>
                <div className="text-sm font-bold text-green-400">{pqc.avg_encrypt_time_ms}ms</div>
              </div>
              <div className="bg-[#151a23] rounded p-2 text-center border border-[#2d3748]">
                <div className="text-[10px] text-gray-500">Decrypt</div>
                <div className="text-sm font-bold text-blue-400">{pqc.avg_decrypt_time_ms}ms</div>
              </div>
              <div className="bg-[#151a23] rounded p-2 text-center border border-[#2d3748]">
                <div className="text-[10px] text-gray-500">Operations</div>
                <div className="text-sm font-bold text-gray-300">{pqc.total_operations.toLocaleString()}</div>
              </div>
            </div>

            {/* Key rotation */}
            <div className="flex items-center justify-between text-[10px] px-2 py-1.5 bg-[#151a23] rounded border border-[#2d3748]">
              <span className="text-gray-500">Last Key Rotation</span>
              <span className="text-gray-300">{new Date(pqc.last_key_rotation).toLocaleDateString()}</span>
            </div>
          </div>
        ) : (
          <div className="text-gray-500 text-xs text-center py-8">PQC data unavailable</div>
        )}
      </div>

      {/* Footer */}
      {pqc && (
        <div className="px-4 py-2 border-t border-[#2d3748] text-[10px] text-gray-500">
          {pqc.compliance}
        </div>
      )}
    </div>
  );
};

export default PQCStatusPanel;
