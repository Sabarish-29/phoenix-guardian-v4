import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldExclamationIcon,
  ExclamationTriangleIcon,
  FingerPrintIcon,
  ChartBarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
} from '@heroicons/react/24/outline';
import { useAppDispatch, useAppSelector } from '../hooks/useStore';
import { fetchThreats, selectThreatStats, selectFilteredThreats } from '../store/slices/threatsSlice';
import { fetchIncidents, selectIncidentsStats } from '../store/slices/incidentsSlice';
import { fetchHoneytokens, selectHoneytokensStats } from '../store/slices/honeytokensSlice';
import { selectFederatedStats, fetchGlobalModel } from '../store/slices/federatedSlice';
import ThreatSeverityChart from '../components/charts/ThreatSeverityChart';
import ThreatTimelineChart from '../components/charts/ThreatTimelineChart';
import RecentThreats from '../components/dashboard/RecentThreats';
import ActiveIncidents from '../components/dashboard/ActiveIncidents';
import clsx from 'clsx';

interface StatCardProps {
  title: string;
  value: number | string;
  change?: number;
  changeLabel?: string;
  icon: React.ComponentType<{ className?: string }>;
  color: 'red' | 'orange' | 'yellow' | 'green' | 'blue' | 'purple';
  href?: string;
}

function StatCard({ title, value, change, changeLabel, icon: Icon, color, href }: StatCardProps) {
  const colorClasses = {
    red: 'bg-red-500/10 text-red-400 border-red-500/20',
    orange: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    yellow: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    green: 'bg-green-500/10 text-green-400 border-green-500/20',
    blue: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    purple: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  };

  const iconColors = {
    red: 'bg-red-500',
    orange: 'bg-orange-500',
    yellow: 'bg-yellow-500',
    green: 'bg-green-500',
    blue: 'bg-blue-500',
    purple: 'bg-purple-500',
  };

  const content = (
    <div className={clsx(
      'p-4 rounded-xl border card-hover',
      colorClasses[color]
    )}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-dashboard-muted">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {change !== undefined && (
            <div className="flex items-center mt-2 text-sm">
              {change >= 0 ? (
                <ArrowTrendingUpIcon className="w-4 h-4 mr-1 text-red-400" />
              ) : (
                <ArrowTrendingDownIcon className="w-4 h-4 mr-1 text-green-400" />
              )}
              <span className={change >= 0 ? 'text-red-400' : 'text-green-400'}>
                {Math.abs(change)}%
              </span>
              <span className="text-dashboard-muted ml-1">{changeLabel}</span>
            </div>
          )}
        </div>
        <div className={clsx('p-2 rounded-lg', iconColors[color])}>
          <Icon className="w-5 h-5 text-white" />
        </div>
      </div>
    </div>
  );

  if (href) {
    return <Link to={href}>{content}</Link>;
  }

  return content;
}

/**
 * Dashboard Home - Main security overview page
 */
export default function DashboardHome() {
  const dispatch = useAppDispatch();
  const threatStats = useAppSelector(selectThreatStats);
  const incidentStats = useAppSelector(selectIncidentsStats);
  const honeytokenStats = useAppSelector(selectHoneytokensStats);
  const federatedStats = useAppSelector(selectFederatedStats);
  const recentThreats = useAppSelector(selectFilteredThreats);

  useEffect(() => {
    dispatch(fetchThreats(undefined));
    dispatch(fetchIncidents(undefined));
    dispatch(fetchHoneytokens());
    dispatch(fetchGlobalModel());
  }, [dispatch]);

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Active Threats"
          value={threatStats.total}
          change={12}
          changeLabel="vs last hour"
          icon={ShieldExclamationIcon}
          color="red"
          href="/threats"
        />
        <StatCard
          title="Critical Alerts"
          value={threatStats.critical}
          change={-5}
          changeLabel="vs yesterday"
          icon={ExclamationTriangleIcon}
          color="orange"
          href="/threats?severity=critical"
        />
        <StatCard
          title="Open Incidents"
          value={incidentStats.open + incidentStats.investigating}
          icon={ExclamationTriangleIcon}
          color="yellow"
          href="/incidents"
        />
        <StatCard
          title="Honeytokens Triggered"
          value={honeytokenStats.triggered}
          icon={FingerPrintIcon}
          color="purple"
          href="/honeytokens"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <h3 className="text-lg font-semibold text-white mb-4">Threat Timeline (24h)</h3>
          <ThreatTimelineChart />
        </div>
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <h3 className="text-lg font-semibold text-white mb-4">Threats by Severity</h3>
          <ThreatSeverityChart stats={threatStats} />
        </div>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Recent Threats</h3>
            <Link
              to="/threats"
              className="text-sm text-phoenix-400 hover:text-phoenix-300"
            >
              View All
            </Link>
          </div>
          <RecentThreats threats={recentThreats.slice(0, 5)} />
        </div>
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Active Incidents</h3>
            <Link
              to="/incidents"
              className="text-sm text-phoenix-400 hover:text-phoenix-300"
            >
              View All
            </Link>
          </div>
          <ActiveIncidents />
        </div>
      </div>

      {/* Federated Network Status */}
      <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <ChartBarIcon className="w-5 h-5 text-phoenix-400" />
            <h3 className="text-lg font-semibold text-white">Federated Threat Intelligence</h3>
          </div>
          <Link
            to="/federated"
            className="text-sm text-phoenix-400 hover:text-phoenix-300"
          >
            View Details
          </Link>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <p className="text-2xl font-bold text-white">{federatedStats.participatingHospitals}</p>
            <p className="text-sm text-dashboard-muted">Hospitals</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-white">{federatedStats.totalSignatures}</p>
            <p className="text-sm text-dashboard-muted">Shared Signatures</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-white">{(federatedStats.avgConfidence * 100).toFixed(0)}%</p>
            <p className="text-sm text-dashboard-muted">Avg Confidence</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-white">{(federatedStats.privacyBudgetUsed * 100).toFixed(1)}%</p>
            <p className="text-sm text-dashboard-muted">Privacy Budget Used</p>
          </div>
        </div>
      </div>
    </div>
  );
}
