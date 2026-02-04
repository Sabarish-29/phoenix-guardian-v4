# ADR-013: Attack Detection Pipeline Architecture

## Status
Accepted

## Date
Day 108 (Phase 3)

## Context

Phoenix Guardian must detect multiple attack types in real-time:
1. Prompt injection attempts
2. Jailbreak attempts
3. Data exfiltration
4. Adversarial audio
5. Honeytoken access

Detection must occur with <500ms latency while maintaining high accuracy (>99.5%) and low false positive rate (<1%).

## Decision

We will implement a multi-stage detection pipeline with parallel analyzers and confidence scoring.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Attack Detection Pipeline                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Input ──► ┌────────────────────────────────────────────────┐   │
│            │              Pre-Processing                     │   │
│            │  - Text normalization                          │   │
│            │  - Feature extraction                          │   │
│            │  - Context enrichment                          │   │
│            └────────────────────────────────────────────────┘   │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         │                    │                    │             │
│         ▼                    ▼                    ▼             │
│  ┌────────────┐       ┌────────────┐       ┌────────────┐      │
│  │  Prompt    │       │  Jailbreak │       │   Data     │      │
│  │ Injection  │       │  Detector  │       │ Exfil Det  │      │
│  │  Detector  │       │            │       │            │      │
│  └─────┬──────┘       └─────┬──────┘       └─────┬──────┘      │
│        │                    │                    │              │
│        └────────────────────┼────────────────────┘              │
│                             ▼                                    │
│            ┌────────────────────────────────────────────────┐   │
│            │           Confidence Aggregator                 │   │
│            │  - Weighted ensemble                           │   │
│            │  - Threshold evaluation                        │   │
│            │  - Severity classification                     │   │
│            └────────────────────────────────────────────────┘   │
│                             │                                    │
│                             ▼                                    │
│            ┌────────────────────────────────────────────────┐   │
│            │            Response Engine                      │   │
│            │  - Alert generation                            │   │
│            │  - Request blocking                            │   │
│            │  - Evidence collection                         │   │
│            └────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from dataclasses import dataclass
from typing import List, Optional
import asyncio

@dataclass
class DetectionResult:
    attack_type: str
    confidence: float
    severity: str
    evidence: dict
    detector: str

class AttackDetectionPipeline:
    def __init__(self):
        self.detectors = [
            PromptInjectionDetector(),
            JailbreakDetector(),
            DataExfiltrationDetector(),
            AdversarialAudioDetector(),
            HoneytokenDetector(),
        ]
        self.thresholds = {
            "critical": 0.95,
            "high": 0.85,
            "medium": 0.70,
            "low": 0.50,
        }
    
    async def analyze(
        self, 
        content: str, 
        context: dict
    ) -> Optional[DetectionResult]:
        # Run all detectors in parallel
        tasks = [
            detector.analyze(content, context)
            for detector in self.detectors
        ]
        results = await asyncio.gather(*tasks)
        
        # Find highest confidence detection
        valid_results = [r for r in results if r and r.confidence > 0.5]
        
        if not valid_results:
            return None
        
        # Return highest confidence result
        return max(valid_results, key=lambda r: r.confidence)
```

## Consequences

### Positive
- Parallel detection minimizes latency
- Modular detectors can be updated independently
- Ensemble approach improves accuracy
- Evidence collection supports investigation

### Negative
- Complex pipeline to maintain
- Resource intensive (multiple models)
- Tuning thresholds requires expertise

## References
- OWASP LLM Top 10: https://owasp.org/www-project-top-10-for-large-language-model-applications/
- Prompt Injection Research Papers
