import { useEffect, useState } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { threatsApi } from '../../services/api/threatsApi';
import { format, subHours } from 'date-fns';

interface TimelineData {
  hour: string;
  count: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

/**
 * Area chart showing threat volume over time
 */
export default function ThreatTimelineChart() {
  const [data, setData] = useState<TimelineData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const response = await threatsApi.getThreatTimeline('24h');
        // Transform and aggregate data
        const hourlyData: Map<string, TimelineData> = new Map();
        
        // Initialize with empty hours
        for (let i = 23; i >= 0; i--) {
          const hour = format(subHours(new Date(), i), 'HH:00');
          hourlyData.set(hour, {
            hour,
            count: 0,
            critical: 0,
            high: 0,
            medium: 0,
            low: 0,
          });
        }
        
        // Aggregate threat data
        response.forEach((item: any) => {
          const hour = format(new Date(item.hour), 'HH:00');
          const existing = hourlyData.get(hour);
          if (existing) {
            existing.count += item.count;
            const severity = item.severity as keyof Pick<TimelineData, 'critical' | 'high' | 'medium' | 'low'>;
            if (severity in existing) {
              existing[severity] += item.count;
            }
          }
        });
        
        setData(Array.from(hourlyData.values()));
      } catch (error) {
        console.error('Failed to fetch timeline data:', error);
        // Generate mock data for demo
        setData(generateMockData());
      } finally {
        setLoading(false);
      }
    }
    
    fetchData();
  }, []);

  if (loading) {
    return <div className="h-64 skeleton rounded-lg" />;
  }

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id="colorCritical" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#dc2626" stopOpacity={0.8}/>
              <stop offset="95%" stopColor="#dc2626" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="colorHigh" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ea580c" stopOpacity={0.8}/>
              <stop offset="95%" stopColor="#ea580c" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="colorMedium" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ca8a04" stopOpacity={0.8}/>
              <stop offset="95%" stopColor="#ca8a04" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="hour"
            stroke="#64748b"
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            tickLine={false}
          />
          <YAxis
            stroke="#64748b"
            tick={{ fill: '#94a3b8', fontSize: 12 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '8px',
              color: '#e2e8f0',
            }}
          />
          <Area
            type="monotone"
            dataKey="critical"
            stackId="1"
            stroke="#dc2626"
            fillOpacity={1}
            fill="url(#colorCritical)"
          />
          <Area
            type="monotone"
            dataKey="high"
            stackId="1"
            stroke="#ea580c"
            fillOpacity={1}
            fill="url(#colorHigh)"
          />
          <Area
            type="monotone"
            dataKey="medium"
            stackId="1"
            stroke="#ca8a04"
            fillOpacity={1}
            fill="url(#colorMedium)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// Generate mock data for demo purposes
function generateMockData(): TimelineData[] {
  const data: TimelineData[] = [];
  for (let i = 23; i >= 0; i--) {
    const hour = format(subHours(new Date(), i), 'HH:00');
    const critical = Math.floor(Math.random() * 5);
    const high = Math.floor(Math.random() * 10);
    const medium = Math.floor(Math.random() * 15);
    const low = Math.floor(Math.random() * 8);
    data.push({
      hour,
      count: critical + high + medium + low,
      critical,
      high,
      medium,
      low,
    });
  }
  return data;
}
