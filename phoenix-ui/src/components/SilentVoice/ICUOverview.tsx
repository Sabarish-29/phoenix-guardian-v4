/**
 * ICUOverview — Compact table of all ICU patients with alert status.
 *
 * Shows: Patient name, Bed, Alert level, Distress duration, Action button.
 * Clicking a patient navigates to the full SilentVoicePage for that patient.
 */

import React, { useEffect, useState } from 'react';
import { silentVoiceService } from '../../api/services/silentVoiceService';
import type { ICUOverview as ICUOverviewData, MonitorResult } from '../../api/services/silentVoiceService';

const alertBadge = (level: string) => {
  switch (level) {
    case 'critical':
      return <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs font-bold rounded-full">🔴 Critical</span>;
    case 'warning':
      return <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs font-bold rounded-full">🟡 Warning</span>;
    default:
      return <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs font-bold rounded-full">✅ Clear</span>;
  }
};

export const ICUOverview: React.FC = () => {
  const [data, setData] = useState<ICUOverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await silentVoiceService.getIcuOverview();
        setData(response.data);
      } catch (e: any) {
        setError(e?.message || 'Failed to load ICU overview');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="bg-white border rounded-lg p-6 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-48 mb-4" />
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-10 bg-gray-200 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
        ⚠️ {error}
      </div>
    );
  }

  return (
    <div className="bg-white border rounded-lg overflow-hidden">
      <div className="px-5 py-3 bg-gray-50 border-b flex items-center justify-between">
        <h3 className="text-sm font-bold text-gray-700">🏥 ICU Overview</h3>
        <span className="text-xs text-gray-500">
          {data?.patients_with_alerts || 0} / {data?.total_patients || 0} patients alerting
        </span>
      </div>

      {(!data || data.results.length === 0) ? (
        <div className="p-6 text-center text-gray-400 text-sm">
          No ICU patients with active alerts
        </div>
      ) : (
        <table className="w-full">
          <thead>
            <tr className="text-xs text-gray-500 border-b">
              <th className="text-left px-4 py-2">Patient</th>
              <th className="text-left px-4 py-2">Alert</th>
              <th className="text-left px-4 py-2">Distress</th>
              <th className="text-left px-4 py-2">Signals</th>
              <th className="text-left px-4 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((result: MonitorResult, idx: number) => (
              <tr key={idx} className="border-b hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3">
                  <div className="font-semibold text-sm text-gray-800">{result.patient_name}</div>
                </td>
                <td className="px-4 py-3">{alertBadge(result.alert_level)}</td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {result.distress_duration_minutes} min
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {result.signals_detected.map(s => s.label).join(', ')}
                </td>
                <td className="px-4 py-3">
                  <a
                    href="/silent-voice"
                    className="text-blue-600 hover:text-blue-700 text-sm font-medium"
                  >
                    View →
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default ICUOverview;
