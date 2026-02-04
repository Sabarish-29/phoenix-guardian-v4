import type { PrivacyMetrics } from '../../types/federated';
import { format } from 'date-fns';

interface PrivacyBudgetGaugeProps {
  metrics: PrivacyMetrics;
}

/**
 * Gauge showing privacy budget usage
 */
export default function PrivacyBudgetGauge({ metrics }: PrivacyBudgetGaugeProps) {
  const usedPercentage = (metrics.budgetUsed / metrics.budgetTotal) * 100;
  const remainingPercentage = 100 - usedPercentage;
  
  // Color based on usage
  const getColor = () => {
    if (usedPercentage < 50) return '#16a34a'; // green
    if (usedPercentage < 75) return '#ca8a04'; // yellow
    if (usedPercentage < 90) return '#ea580c'; // orange
    return '#dc2626'; // red
  };

  const strokeDasharray = 283; // Circumference of circle with r=45
  const strokeDashoffset = strokeDasharray * (1 - usedPercentage / 100);

  return (
    <div className="space-y-4">
      {/* Circular Gauge */}
      <div className="flex justify-center">
        <div className="relative w-40 h-40">
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
            {/* Background circle */}
            <circle
              cx="50"
              cy="50"
              r="45"
              fill="none"
              stroke="#334155"
              strokeWidth="8"
            />
            {/* Progress circle */}
            <circle
              cx="50"
              cy="50"
              r="45"
              fill="none"
              stroke={getColor()}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={strokeDasharray}
              strokeDashoffset={strokeDashoffset}
              className="transition-all duration-500"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold text-white">{usedPercentage.toFixed(1)}%</span>
            <span className="text-xs text-dashboard-muted">Used</span>
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-dashboard-muted">Epsilon (ε)</span>
          <span className="text-white">{metrics.epsilon}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-dashboard-muted">Delta (δ)</span>
          <span className="text-white">{metrics.delta}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-dashboard-muted">Queries This Period</span>
          <span className="text-white">{metrics.queriesThisPeriod}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-dashboard-muted">Noise Multiplier</span>
          <span className="text-white">{metrics.noiseMultiplier}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-dashboard-muted">Next Reset</span>
          <span className="text-white">{format(new Date(metrics.nextReset), 'MMM d, HH:mm')}</span>
        </div>
      </div>

      {/* Warning if budget is low */}
      {remainingPercentage < 20 && (
        <div className="p-2 bg-red-500/20 border border-red-500/30 rounded-lg text-center">
          <p className="text-sm text-red-400">
            ⚠️ Privacy budget running low ({remainingPercentage.toFixed(1)}% remaining)
          </p>
        </div>
      )}
    </div>
  );
}
