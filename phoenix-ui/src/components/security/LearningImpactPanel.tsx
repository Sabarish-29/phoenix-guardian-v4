/**
 * Learning Impact Panel.
 *
 * Visualizes how security threat signals feedback into clinical AI
 * model improvement — the "bidirectional learning" story.
 * Uses recharts BarChart for F1 score improvements.
 */

import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import apiClient from '../../api/client';

interface LearningImpact {
  metric_name: string;
  category: string;
  before_f1: number;
  after_f1: number;
  improvement_pct: number;
  sample_count: number;
  last_updated: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  'threat-detection': '#f87171',
  'deception-detection': '#fbbf24',
  'insider-threat': '#a78bfa',
  'input-validation': '#34d399',
  'content-sanitization': '#60a5fa',
};

export const LearningImpactPanel: React.FC = () => {
  const [impacts, setImpacts] = useState<LearningImpact[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await apiClient.get('/security-console/learning-impact');
        setImpacts(res.data.impacts || []);
      } catch (err) {
        console.error('Failed to fetch learning impacts', err);
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, []);

  const chartData = impacts.map((i) => ({
    name: i.metric_name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
    category: i.category,
    before: +(i.before_f1 * 100).toFixed(1),
    after: +(i.after_f1 * 100).toFixed(1),
    improvement: +i.improvement_pct.toFixed(1),
  }));

  const totalImprovement = impacts.reduce((sum, i) => sum + i.improvement_pct, 0) / (impacts.length || 1);

  return (
    <div className="bg-[#1a1f29] border border-[#2d3748] rounded-lg overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#2d3748] flex items-center gap-2">
        <span className="text-lg">🧠</span>
        <h3 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">Security → Clinical Learning</h3>
        <span className="ml-auto text-xs text-green-400 font-bold">
          +{totalImprovement.toFixed(1)}% avg improvement
        </span>
      </div>

      <div className="flex-1 p-4">
        {loading ? (
          <div className="flex items-center justify-center h-full text-gray-500 text-xs">Loading…</div>
        ) : (
          <>
            {/* Chart */}
            <div style={{ height: 180 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" />
                  <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 9 }} angle={-15} textAnchor="end" height={45} />
                  <YAxis tick={{ fill: '#9ca3af', fontSize: 10 }} domain={[60, 100]} unit="%" />
                  <Tooltip
                    contentStyle={{ background: '#1a1f29', border: '1px solid #2d3748', borderRadius: 6, fontSize: 11 }}
                    labelStyle={{ color: '#e5e7eb' }}
                  />
                  <Bar dataKey="before" name="Before (F1%)" fill="#4b5563" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="after" name="After (F1%)" radius={[2, 2, 0, 0]}>
                    {chartData.map((entry, idx) => (
                      <Cell key={idx} fill={CATEGORY_COLORS[entry.category] || '#60a5fa'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Metrics table */}
            <div className="mt-3 space-y-1">
              {impacts.map((i) => (
                <div key={i.metric_name} className="flex items-center justify-between text-[10px] px-2 py-1 rounded hover:bg-[#232a36]">
                  <div className="flex items-center gap-2">
                    <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: CATEGORY_COLORS[i.category] || '#60a5fa' }} />
                    <span className="text-gray-300">{i.metric_name.replace(/_/g, ' ')}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-gray-500">{(i.before_f1 * 100).toFixed(1)}%</span>
                    <span className="text-gray-400">→</span>
                    <span className="text-gray-200 font-bold">{(i.after_f1 * 100).toFixed(1)}%</span>
                    <span className="text-green-400 font-bold">+{i.improvement_pct.toFixed(1)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-[#2d3748] text-[10px] text-gray-500">
        Bidirectional learning: Security threats refine clinical AI models via federated feedback loops
      </div>
    </div>
  );
};

export default LearningImpactPanel;
