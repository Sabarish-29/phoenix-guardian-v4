/**
 * Admin Reports Page — Compliance report generation for admins.
 *
 * Allows generating security reports in PDF/CSV/JSON format,
 * viewing report history, and exporting audit data.
 */

import React, { useState } from 'react';
import apiClient from '../api/client';

interface GeneratedReport {
  id: string;
  name: string;
  type: string;
  format: string;
  date: string;
  size: string;
}

const MOCK_REPORTS: GeneratedReport[] = [
  { id: '1', name: 'Threat Summary — Feb 1–7, 2026', type: 'threat_summary', format: 'PDF', date: '2026-02-07', size: '2.4 MB' },
  { id: '2', name: 'Audit Logs — January 2026', type: 'audit_logs', format: 'CSV', date: '2026-02-01', size: '1.1 MB' },
  { id: '3', name: 'Honeytoken Activity — Q1 2026', type: 'honeytoken', format: 'JSON', date: '2026-01-31', size: '340 KB' },
  { id: '4', name: 'Learning Impact Report — Feb 2026', type: 'learning', format: 'PDF', date: '2026-02-05', size: '1.8 MB' },
];

export const AdminReportsPage: React.FC = () => {
  const [reportType, setReportType] = useState('threat_summary');
  const [startDate, setStartDate] = useState('2026-02-01');
  const [endDate, setEndDate] = useState('2026-02-07');
  const [format, setFormat] = useState('json');
  const [generating, setGenerating] = useState(false);
  const [downloadData, setDownloadData] = useState<string | null>(null);

  const handleGenerate = async () => {
    setGenerating(true);
    setDownloadData(null);
    try {
      // Fetch live data from security console endpoints based on report type
      let data: any;
      if (reportType === 'threat_summary') {
        const [summaryRes, eventsRes] = await Promise.all([
          apiClient.get('/security-console/summary'),
          apiClient.get('/security-console/events?limit=200'),
        ]);
        data = { summary: summaryRes.data, events: eventsRes.data.events, generated_at: new Date().toISOString(), report_type: 'Threat Summary' };
      } else if (reportType === 'honeytoken') {
        const res = await apiClient.get('/security-console/honeytokens');
        data = { ...res.data, generated_at: new Date().toISOString(), report_type: 'Honeytoken Activity' };
      } else if (reportType === 'learning') {
        const res = await apiClient.get('/security-console/learning-impact');
        data = { ...res.data, generated_at: new Date().toISOString(), report_type: 'Learning Impact' };
      } else if (reportType === 'audit_logs') {
        const res = await apiClient.get('/security-console/events?limit=200');
        data = { events: res.data.events, generated_at: new Date().toISOString(), report_type: 'Audit Logs' };
      }

      if (format === 'json') {
        setDownloadData(JSON.stringify(data, null, 2));
      } else if (format === 'csv') {
        // Simple CSV from events
        const events = data.events || data.honeytokens || data.impacts || [];
        if (events.length > 0) {
          const headers = Object.keys(events[0]).join(',');
          const rows = events.map((e: any) => Object.values(e).map((v: any) => `"${String(v).replace(/"/g, '""')}"`).join(','));
          setDownloadData([headers, ...rows].join('\n'));
        } else {
          setDownloadData('No data available');
        }
      }
    } catch (err) {
      console.error('Failed to generate report', err);
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = () => {
    if (!downloadData) return;
    const ext = format === 'csv' ? 'csv' : 'json';
    const mime = format === 'csv' ? 'text/csv' : 'application/json';
    const blob = new Blob([downloadData], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `phoenix_guardian_${reportType}_${startDate}_to_${endDate}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">📊 Security Reports</h1>
        <p className="text-gray-500 mt-1 text-sm">Generate compliance reports for auditing and regulatory review</p>
      </div>

      {/* Report Generator */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Generate Report</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Report Type</label>
            <select value={reportType} onChange={(e) => setReportType(e.target.value)} className="input-field text-sm">
              <option value="threat_summary">Threat Summary</option>
              <option value="audit_logs">Audit Logs</option>
              <option value="honeytoken">Honeytoken Activity</option>
              <option value="learning">Learning Impact</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Start Date</label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="input-field text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">End Date</label>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="input-field text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Format</label>
            <select value={format} onChange={(e) => setFormat(e.target.value)} className="input-field text-sm">
              <option value="json">JSON</option>
              <option value="csv">CSV</option>
            </select>
          </div>
        </div>
        <div className="flex gap-3">
          <button onClick={handleGenerate} disabled={generating} className="btn-primary text-sm">
            {generating ? 'Generating…' : 'Generate Report'}
          </button>
          {downloadData && (
            <button onClick={handleDownload} className="btn-secondary text-sm">
              ⬇ Download {format.toUpperCase()}
            </button>
          )}
        </div>

        {/* Preview */}
        {downloadData && (
          <div className="mt-4 bg-gray-50 border border-gray-200 rounded-lg p-4 max-h-64 overflow-auto">
            <pre className="text-xs text-gray-700 whitespace-pre-wrap">{downloadData.slice(0, 2000)}{downloadData.length > 2000 ? '\n\n... (truncated)' : ''}</pre>
          </div>
        )}
      </div>

      {/* Recent Reports */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Reports</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500 text-xs uppercase">
              <th className="pb-2 pr-4">Report</th>
              <th className="pb-2 pr-4">Format</th>
              <th className="pb-2 pr-4">Date</th>
              <th className="pb-2 pr-4">Size</th>
              <th className="pb-2 text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {MOCK_REPORTS.map((r) => (
              <tr key={r.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-3 pr-4 text-gray-800">{r.name}</td>
                <td className="py-3 pr-4">
                  <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs font-medium">{r.format}</span>
                </td>
                <td className="py-3 pr-4 text-gray-500 text-xs">{r.date}</td>
                <td className="py-3 pr-4 text-gray-500 text-xs">{r.size}</td>
                <td className="py-3 text-right">
                  <button className="text-blue-600 hover:text-blue-800 text-xs font-medium">Download</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Compliance info */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-xs text-blue-800">
        <strong>Compliance Note:</strong> Reports include HIPAA §164.312(b) audit controls data.
        All IP addresses are anonymized and no raw PHI is included in security reports.
        Retain reports per your organization&apos;s data retention policy (minimum 6 years per HIPAA).
      </div>
    </div>
  );
};

export default AdminReportsPage;
