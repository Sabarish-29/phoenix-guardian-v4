import { format } from 'date-fns';
import { ShieldCheckIcon } from '@heroicons/react/24/outline';
import type { ThreatSignature } from '../../types/federated';

interface SignatureListProps {
  signatures: ThreatSignature[];
}

/**
 * List of federated threat signatures
 */
export default function SignatureList({ signatures }: SignatureListProps) {
  if (signatures.length === 0) {
    return (
      <div className="text-center py-12 text-dashboard-muted">
        <ShieldCheckIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
        <p>No threat signatures available</p>
      </div>
    );
  }

  return (
    <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
      {signatures.map((signature) => (
        <div
          key={signature.id}
          className="p-3 bg-dashboard-bg rounded-lg hover:bg-dashboard-border transition-colors"
        >
          <div className="flex items-start justify-between mb-2">
            <div className="flex-1 min-w-0">
              <p className="text-white font-mono text-sm truncate">
                {signature.signatureHash.slice(0, 16)}...
              </p>
              <p className="text-xs text-dashboard-muted capitalize">
                {signature.attackType.replace(/_/g, ' ')}
              </p>
            </div>
            <div className="text-right">
              <p className="text-white font-medium">{(signature.confidence * 100).toFixed(0)}%</p>
              <p className="text-xs text-dashboard-muted">confidence</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4 text-xs text-dashboard-muted">
            <span>{signature.contributorCount} contributors</span>
            <span>•</span>
            <span>First seen: {format(new Date(signature.firstSeen), 'MMM d')}</span>
            {signature.privacyPreserved && (
              <>
                <span>•</span>
                <span className="text-green-400">DP Protected</span>
              </>
            )}
          </div>

          {signature.mitreMapping.length > 0 && (
            <div className="flex gap-1 mt-2">
              {signature.mitreMapping.slice(0, 3).map((id) => (
                <span key={id} className="px-1.5 py-0.5 bg-purple-500/20 text-purple-400 rounded text-xs">
                  {id}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
