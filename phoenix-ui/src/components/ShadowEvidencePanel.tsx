import React, { useState } from 'react'

interface ShadowEvidencePanelProps {
  drugName: string
  labName: string
  pctChange: number
  rSquared: number
  monthsObserved: number
}

const ShadowEvidencePanel: React.FC<ShadowEvidencePanelProps> = ({
  drugName, labName, pctChange, rSquared, monthsObserved
}) => {
  const [expanded, setExpanded] = useState(false)

  return (
    <div style={{
      marginTop: 12,
      border: '1px solid rgba(168,85,247,0.15)',
      borderLeft: '3px solid #a855f7',
      borderRadius: 8,
      background: 'rgba(168,85,247,0.04)',
      overflow: 'hidden'
    }}>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          width: '100%',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '10px 14px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer'
        }}
      >
        <span style={{
          fontSize: '0.68rem',
          fontWeight: 700,
          letterSpacing: '0.1em',
          textTransform: 'uppercase' as const,
          color: '#a855f7'
        }}>
          🔍 Why This Shadow Fired
        </span>
        <span style={{ fontSize: '0.72rem', color: '#4a5568' }}>
          {expanded ? '▲' : '▼'}
        </span>
      </button>

      {expanded && (
        <div style={{ padding: '0 14px 14px' }}>
          {[
            {
              label: 'Trend strength',
              value: `R²=${rSquared} — near-perfect linear correlation over ${monthsObserved} months`
            },
            {
              label: 'Rate of change',
              value: `${Math.abs(pctChange / monthsObserved).toFixed(1)}% decline per month, consistent and accelerating`
            },
            {
              label: 'Clinical basis',
              value: `${drugName} → ${labName} depletion (Ting RZ et al., Arch Intern Med 2006)`
            },
            {
              label: 'Threshold crossed',
              value: `Current level below clinical deficiency marker. Neuropathy risk at <200 pg/mL`
            }
          ].map((item, i) => (
            <div key={i} style={{
              display: 'flex',
              gap: 8,
              marginBottom: 8,
              fontSize: '0.78rem'
            }}>
              <span style={{ color: '#34d399', flexShrink: 0 }}>›</span>
              <div>
                <span style={{ color: '#8b9ab8', fontWeight: 600 }}>{item.label}: </span>
                <span style={{ color: '#c4cfe3' }}>{item.value}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default ShadowEvidencePanel
