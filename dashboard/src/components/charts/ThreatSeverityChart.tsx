import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from 'recharts';

interface ThreatSeverityChartProps {
  stats: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
}

const COLORS = {
  critical: '#dc2626',
  high: '#ea580c',
  medium: '#ca8a04',
  low: '#16a34a',
};

/**
 * Pie chart showing threat distribution by severity
 */
export default function ThreatSeverityChart({ stats }: ThreatSeverityChartProps) {
  const data = [
    { name: 'Critical', value: stats.critical, color: COLORS.critical },
    { name: 'High', value: stats.high, color: COLORS.high },
    { name: 'Medium', value: stats.medium, color: COLORS.medium },
    { name: 'Low', value: stats.low, color: COLORS.low },
  ].filter(item => item.value > 0);

  if (data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-dashboard-muted">
        No threat data available
      </div>
    );
  }

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            paddingAngle={2}
            dataKey="value"
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
            labelLine={false}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '8px',
              color: '#e2e8f0',
            }}
          />
          <Legend
            formatter={(value) => <span className="text-dashboard-text">{value}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
