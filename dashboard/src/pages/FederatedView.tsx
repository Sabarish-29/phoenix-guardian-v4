import { useEffect } from 'react';
import {
  GlobeAltIcon,
  ShieldCheckIcon,
  LockClosedIcon,
  ArrowPathIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';
import { useAppDispatch, useAppSelector } from '../hooks/useStore';
import {
  fetchGlobalModel,
  fetchThreatSignatures,
  fetchPrivacyMetrics,
  fetchContributions,
  selectGlobalModel,
  selectThreatSignatures,
  selectPrivacyMetrics,
  selectContributions,
  selectFederatedLoading,
  selectFederatedStats,
  triggerModelSync,
} from '../store/slices/federatedSlice';
import SignatureList from '../components/federated/SignatureList';
import PrivacyBudgetGauge from '../components/federated/PrivacyBudgetGauge';
import ContributionMap from '../components/federated/ContributionMap';
import { format } from 'date-fns';

/**
 * FederatedView - Federated threat intelligence network dashboard
 */
export default function FederatedView() {
  const dispatch = useAppDispatch();
  const globalModel = useAppSelector(selectGlobalModel);
  const signatures = useAppSelector(selectThreatSignatures);
  const privacyMetrics = useAppSelector(selectPrivacyMetrics);
  const contributions = useAppSelector(selectContributions);
  const loading = useAppSelector(selectFederatedLoading);
  const stats = useAppSelector(selectFederatedStats);

  useEffect(() => {
    dispatch(fetchGlobalModel());
    dispatch(fetchThreatSignatures(undefined));
    dispatch(fetchPrivacyMetrics());
    dispatch(fetchContributions());
  }, [dispatch]);

  const handleSync = () => {
    dispatch(triggerModelSync());
  };

  return (
    <div className="space-y-6">
      {/* Header Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <GlobeAltIcon className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <p className="text-dashboard-muted text-sm">Hospitals</p>
              <p className="text-xl font-bold text-white">{stats.participatingHospitals}</p>
            </div>
          </div>
        </div>
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500/20 rounded-lg">
              <ShieldCheckIcon className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <p className="text-dashboard-muted text-sm">Signatures</p>
              <p className="text-xl font-bold text-white">{stats.totalSignatures}</p>
            </div>
          </div>
        </div>
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <ChartBarIcon className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <p className="text-dashboard-muted text-sm">Avg Confidence</p>
              <p className="text-xl font-bold text-white">{(stats.avgConfidence * 100).toFixed(0)}%</p>
            </div>
          </div>
        </div>
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-orange-500/20 rounded-lg">
              <LockClosedIcon className="w-5 h-5 text-orange-400" />
            </div>
            <div>
              <p className="text-dashboard-muted text-sm">Privacy Budget</p>
              <p className="text-xl font-bold text-white">{(stats.privacyBudgetUsed * 100).toFixed(1)}%</p>
            </div>
          </div>
        </div>
      </div>

      {/* Model Status */}
      <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Global Model Status</h3>
          <button
            onClick={handleSync}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-phoenix-500 text-white rounded-lg hover:bg-phoenix-600 transition-colors disabled:opacity-50"
          >
            <ArrowPathIcon className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Sync Now
          </button>
        </div>
        {globalModel ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div>
              <p className="text-dashboard-muted text-sm">Version</p>
              <p className="text-white font-medium">{globalModel.version}</p>
            </div>
            <div>
              <p className="text-dashboard-muted text-sm">Last Updated</p>
              <p className="text-white font-medium">
                {format(new Date(globalModel.lastUpdated), 'MMM d, HH:mm')}
              </p>
            </div>
            <div>
              <p className="text-dashboard-muted text-sm">Accuracy</p>
              <p className="text-white font-medium">{(globalModel.accuracy * 100).toFixed(1)}%</p>
            </div>
            <div>
              <p className="text-dashboard-muted text-sm">Privacy (ε, δ)</p>
              <p className="text-white font-medium">
                ε={globalModel.privacyGuarantee.epsilon}, δ={globalModel.privacyGuarantee.delta}
              </p>
            </div>
          </div>
        ) : (
          <div className="h-20 skeleton rounded-lg" />
        )}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Signatures List */}
        <div className="lg:col-span-2 bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <h3 className="text-lg font-semibold text-white mb-4">Threat Signatures</h3>
          <SignatureList signatures={signatures} />
        </div>

        {/* Privacy Budget */}
        <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
          <h3 className="text-lg font-semibold text-white mb-4">Privacy Budget</h3>
          {privacyMetrics ? (
            <PrivacyBudgetGauge metrics={privacyMetrics} />
          ) : (
            <div className="h-48 skeleton rounded-lg" />
          )}
        </div>
      </div>

      {/* Contribution Map */}
      <div className="bg-dashboard-card rounded-xl border border-dashboard-border p-4">
        <h3 className="text-lg font-semibold text-white mb-4">Hospital Contributions</h3>
        <ContributionMap contributions={contributions} />
      </div>
    </div>
  );
}
