import type { HospitalContribution } from '../../types/federated';

interface ContributionMapProps {
  contributions: HospitalContribution[];
}

/**
 * Map/table showing hospital contributions to federated network
 */
export default function ContributionMap({ contributions }: ContributionMapProps) {
  if (contributions.length === 0) {
    return (
      <div className="text-center py-12 text-dashboard-muted">
        <p>No contributions data available</p>
      </div>
    );
  }

  // Group by region
  const byRegion = contributions.reduce((acc, c) => {
    if (!acc[c.region]) acc[c.region] = [];
    acc[c.region].push(c);
    return acc;
  }, {} as Record<string, HospitalContribution[]>);

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="text-center p-3 bg-dashboard-bg rounded-lg">
          <p className="text-2xl font-bold text-white">{contributions.length}</p>
          <p className="text-xs text-dashboard-muted">Hospitals</p>
        </div>
        <div className="text-center p-3 bg-dashboard-bg rounded-lg">
          <p className="text-2xl font-bold text-white">
            {contributions.reduce((sum, c) => sum + c.contributionCount, 0)}
          </p>
          <p className="text-xs text-dashboard-muted">Total Contributions</p>
        </div>
        <div className="text-center p-3 bg-dashboard-bg rounded-lg">
          <p className="text-2xl font-bold text-white">
            {(contributions.reduce((sum, c) => sum + c.qualityScore, 0) / contributions.length * 100).toFixed(0)}%
          </p>
          <p className="text-xs text-dashboard-muted">Avg Quality</p>
        </div>
      </div>

      {/* By Region */}
      <div className="space-y-4">
        {Object.entries(byRegion).map(([region, hospitals]) => (
          <div key={region} className="bg-dashboard-bg rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-white font-medium">{region}</h4>
              <span className="text-sm text-dashboard-muted">{hospitals.length} hospitals</span>
            </div>
            <div className="space-y-2">
              {hospitals.slice(0, 3).map((hospital) => (
                <div key={hospital.hospitalId} className="flex items-center justify-between text-sm">
                  <span className="text-dashboard-text truncate">{hospital.hospitalName}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-dashboard-muted">{hospital.contributionCount} contrib.</span>
                    <span className={hospital.privacyCompliant ? 'text-green-400' : 'text-red-400'}>
                      {hospital.privacyCompliant ? '✓' : '✗'}
                    </span>
                  </div>
                </div>
              ))}
              {hospitals.length > 3 && (
                <p className="text-xs text-dashboard-muted">
                  +{hospitals.length - 3} more hospitals
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
