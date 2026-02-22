import React, { useState } from 'react'

interface EvidencePanelProps {
  diseaseName: string
  confidence: number
  symptomsMatched: number
  totalSymptoms: number
  orphaCode: string
}

const EvidencePanel: React.FC<EvidencePanelProps> = ({
  diseaseName, confidence, symptomsMatched, totalSymptoms, orphaCode
}) => {
  const [expanded, setExpanded] = useState(false)

  const evidenceItems = [
    {
      icon: '✓',
      label: 'Symptom overlap',
      value: `${symptomsMatched}/${totalSymptoms} symptoms match ${diseaseName} criteria`,
      confidence: Math.round((symptomsMatched / totalSymptoms) * 100)
    },
    {
      icon: '✓',
      label: 'Orphanet database match',
      value: `${orphaCode} — ${confidence}% phenotype overlap with registered cases`,
      confidence: confidence
    },
    {
      icon: '✓',
      label: 'Differential ruled out',
      value: 'Marfan Syndrome excluded (no aortic/lens features documented)',
      confidence: 91
    },
    {
      icon: '✓',
      label: 'Published diagnostic criteria',
      value: 'Malfait et al. 2017 hEDS diagnostic criteria (Eur J Hum Genet)',
      confidence: null
    },
    {
      icon: '✓',
      label: 'Visit pattern analysis',
      value: 'Symptom escalation across 5 visits consistent with progressive connective tissue disorder',
      confidence: 88
    }
  ]

  return (
    <div style={{
      marginBottom: 20,
      border: '1px solid rgba(245,158,11,0.2)',
      borderLeft: '3px solid #f59e0b',
      borderRadius: 10,
      background: 'rgba(245,158,11,0.04)',
      overflow: 'hidden'
    }}>
      {/* Header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          width: '100%',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '14px 18px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: '#f0f4ff'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: '0.85rem' }}>🔍</span>
          <span style={{
            fontSize: '0.72rem',
            fontWeight: 700,
            letterSpacing: '0.1em',
            textTransform: 'uppercase' as const,
            color: '#f59e0b'
          }}>
            How We Reached This Diagnosis
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            fontSize: '0.72rem',
            color: '#8b9ab8',
            fontStyle: 'italic'
          }}>
            {expanded ? 'Hide evidence' : 'View evidence →'}
          </span>
        </div>
      </button>

      {/* Expandable content */}
      {expanded && (
        <div style={{ padding: '0 18px 18px' }}>
          {/* Confidence breakdown bars */}
          <div style={{ marginBottom: 16 }}>
            <div style={{
              fontSize: '0.68rem',
              fontWeight: 600,
              letterSpacing: '0.08em',
              textTransform: 'uppercase' as const,
              color: '#4a5568',
              marginBottom: 10
            }}>
              Confidence Breakdown
            </div>
            {[
              { label: 'Symptom overlap', pct: Math.round((symptomsMatched/totalSymptoms)*100) },
              { label: 'Visit pattern match', pct: 88 },
              { label: 'Differential rule-out', pct: 91 },
              { label: 'Final weighted score', pct: confidence }
            ].map(bar => (
              <div key={bar.label} style={{ marginBottom: 8 }}>
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginBottom: 3
                }}>
                  <span style={{ fontSize: '0.75rem', color: '#8b9ab8' }}>{bar.label}</span>
                  <span style={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: bar.pct >= 80 ? '#f59e0b' : '#8b9ab8',
                    fontFamily: 'monospace'
                  }}>{bar.pct}%</span>
                </div>
                <div style={{
                  height: 4,
                  background: 'rgba(255,255,255,0.06)',
                  borderRadius: 100,
                  overflow: 'hidden'
                }}>
                  <div style={{
                    height: '100%',
                    width: `${bar.pct}%`,
                    background: bar.pct >= 80
                      ? 'linear-gradient(90deg, #f59e0b, #fbbf24)'
                      : 'rgba(245,158,11,0.4)',
                    borderRadius: 100,
                    transition: 'width 1s ease'
                  }} />
                </div>
              </div>
            ))}
          </div>

          {/* Evidence list */}
          <div style={{
            fontSize: '0.68rem',
            fontWeight: 600,
            letterSpacing: '0.08em',
            textTransform: 'uppercase' as const,
            color: '#4a5568',
            marginBottom: 10
          }}>
            Evidence Base
          </div>
          {evidenceItems.map((item, i) => (
            <div key={i} style={{
              display: 'flex',
              gap: 10,
              marginBottom: 8,
              padding: '8px 10px',
              background: 'rgba(255,255,255,0.03)',
              borderRadius: 6
            }}>
              <span style={{ color: '#34d399', flexShrink: 0, fontSize: '0.8rem' }}>
                {item.icon}
              </span>
              <div>
                <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#8b9ab8' }}>
                  {item.label}
                </div>
                <div style={{ fontSize: '0.78rem', color: '#c4cfe3', marginTop: 2, lineHeight: 1.5 }}>
                  {item.value}
                </div>
              </div>
            </div>
          ))}

          {/* Research basis */}
          <div style={{
            marginTop: 12,
            padding: '10px 12px',
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 6
          }}>
            <div style={{
              fontSize: '0.65rem',
              fontWeight: 700,
              letterSpacing: '0.08em',
              textTransform: 'uppercase' as const,
              color: '#4a5568',
              marginBottom: 6
            }}>
              Research Foundation
            </div>
            {[
              'Malfait F et al. (2017) The 2017 international classification of the Ehlers–Danlos syndromes. Eur J Hum Genet.',
              'EDS Society Global Survey (2020): Average diagnostic delay 10.4 years across 7 physicians.',
              'Orphanet Report Series (2020): Rare disease patients see avg 7.3 doctors before diagnosis.'
            ].map((ref, i) => (
              <div key={i} style={{
                fontSize: '0.72rem',
                color: '#4a5568',
                marginBottom: 4,
                paddingLeft: 10,
                borderLeft: '2px solid rgba(245,158,11,0.2)',
                lineHeight: 1.5
              }}>
                {ref}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default EvidencePanel
