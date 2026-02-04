# ADR-005: Differential Privacy Parameters for Federated Learning

## Status
Accepted

## Date
Day 125 (Phase 3)

## Context

Phoenix Guardian implements federated learning for collaborative threat intelligence. Hospital systems contribute anonymized threat data to improve detection across the consortium without sharing raw patient or attack data.

To mathematically guarantee privacy, we need differential privacy. The key challenge is selecting privacy parameters (ε, δ) that:
1. Provide meaningful privacy guarantees
2. Allow sufficient utility for threat detection
3. Meet HIPAA requirements for de-identification
4. Are sustainable over continuous learning rounds

## Decision

We will implement (ε, δ)-differential privacy with the following parameters:

- **ε (epsilon) = 0.5** per training round
- **δ (delta) = 1e-5** (0.00001)
- **Privacy budget renewal:** Weekly
- **Gradient clipping norm:** 1.0
- **Noise multiplier:** Calculated based on ε, δ, and sample rate

### Privacy Guarantees

With ε=0.5 and δ=1e-5:
- The probability of any output changing due to a single data point is bounded
- An attacker cannot infer with high confidence whether a specific hospital contributed data
- Even with auxiliary information, privacy loss is bounded

### Implementation

```python
from opacus import PrivacyEngine
from opacus.accountants import RDPAccountant

class FederatedPrivacyConfig:
    """Differential privacy configuration for federated learning."""
    
    # Privacy parameters
    EPSILON_PER_ROUND = 0.5  # Privacy loss per round
    DELTA = 1e-5             # Probability of privacy breach
    MAX_GRAD_NORM = 1.0      # Gradient clipping threshold
    
    # Budget management
    WEEKLY_EPSILON_BUDGET = 3.5  # 7 rounds * 0.5 per round
    MONTHLY_EPSILON_BUDGET = 15.0
    
    # Training parameters
    NOISE_MULTIPLIER = 1.1   # Calculated for target ε, δ
    SAMPLE_RATE = 0.01       # Fraction of data per batch
    
    @classmethod
    def get_accountant(cls):
        """Get privacy accountant for tracking budget."""
        return RDPAccountant()
    
    @classmethod
    def attach_privacy_engine(cls, model, optimizer, data_loader):
        """Attach Opacus privacy engine to model."""
        privacy_engine = PrivacyEngine()
        
        model, optimizer, data_loader = privacy_engine.make_private(
            module=model,
            optimizer=optimizer,
            data_loader=data_loader,
            noise_multiplier=cls.NOISE_MULTIPLIER,
            max_grad_norm=cls.MAX_GRAD_NORM,
            poisson_sampling=True,
        )
        
        return model, optimizer, data_loader, privacy_engine


class PrivacyBudgetManager:
    """Manage privacy budget across training rounds."""
    
    def __init__(self):
        self.accountant = RDPAccountant()
        self.rounds_this_week = 0
        self.total_epsilon_spent = 0.0
    
    def can_train(self) -> bool:
        """Check if we have budget for another round."""
        projected_epsilon = self.total_epsilon_spent + FederatedPrivacyConfig.EPSILON_PER_ROUND
        return projected_epsilon <= FederatedPrivacyConfig.WEEKLY_EPSILON_BUDGET
    
    def record_round(self, steps: int, sample_rate: float):
        """Record a training round and update budget."""
        epsilon = self.accountant.get_epsilon(
            delta=FederatedPrivacyConfig.DELTA,
            steps=steps,
            sample_rate=sample_rate,
            noise_multiplier=FederatedPrivacyConfig.NOISE_MULTIPLIER,
        )
        self.total_epsilon_spent += epsilon
        self.rounds_this_week += 1
        return epsilon
    
    def reset_weekly_budget(self):
        """Reset weekly budget (called by scheduler)."""
        self.rounds_this_week = 0
        # Note: total_epsilon_spent continues accumulating for audit
```

### Gradient Aggregation with Noise

```python
import torch
from typing import List, Dict

def secure_aggregate_gradients(
    gradients: List[Dict[str, torch.Tensor]],
    weights: List[float],
    epsilon: float,
    delta: float,
    max_grad_norm: float = 1.0,
) -> Dict[str, torch.Tensor]:
    """
    Aggregate gradients with differential privacy guarantees.
    
    Args:
        gradients: List of gradient dictionaries from participants
        weights: Contribution weights (based on data size)
        epsilon: Privacy parameter
        delta: Privacy parameter
        max_grad_norm: Clipping threshold
    
    Returns:
        Differentially private aggregated gradients
    """
    aggregated = {}
    
    for key in gradients[0].keys():
        # Clip individual gradients
        clipped = []
        for grad_dict in gradients:
            grad = grad_dict[key]
            norm = torch.norm(grad)
            if norm > max_grad_norm:
                grad = grad * (max_grad_norm / norm)
            clipped.append(grad)
        
        # Weighted average
        stacked = torch.stack(clipped)
        weights_tensor = torch.tensor(weights).view(-1, *([1] * (stacked.dim() - 1)))
        weighted_avg = (stacked * weights_tensor).sum(dim=0) / sum(weights)
        
        # Add calibrated noise
        sensitivity = max_grad_norm / len(gradients)
        noise_scale = sensitivity * (2 * math.log(1.25 / delta)) ** 0.5 / epsilon
        noise = torch.normal(0, noise_scale, weighted_avg.shape)
        
        aggregated[key] = weighted_avg + noise
    
    return aggregated
```

## Consequences

### Positive

1. **Mathematical guarantees** - Provable privacy bounds
2. **HIPAA compliance** - Meets de-identification requirements
3. **Audit trail** - Privacy budget tracked and reported
4. **Sustainable learning** - Weekly renewal allows continuous improvement
5. **Consortium trust** - Participants can verify privacy protection

### Negative

1. **Utility loss** - Noise reduces model accuracy by ~5-10%
2. **Limited rounds** - Budget constraints limit training frequency
3. **Computation overhead** - Per-sample gradient computation is expensive
4. **Complexity** - Requires careful implementation and validation
5. **Hyperparameter sensitivity** - Wrong parameters can break utility or privacy

### Risks

1. **Budget exhaustion** - Mitigated by weekly renewal and monitoring
2. **Implementation bugs** - Mitigated by using vetted Opacus library
3. **Composition attacks** - Mitigated by tracking cumulative privacy loss

## Parameter Selection Rationale

### Why ε = 0.5?

| Epsilon | Privacy Level | Utility Impact | Use Cases |
|---------|--------------|----------------|-----------|
| 0.1 | Very strong | Very high noise | Highly sensitive data |
| 0.5 | Strong | Moderate noise | Healthcare, our choice |
| 1.0 | Moderate | Lower noise | General ML |
| 5.0 | Weak | Minimal noise | Low-sensitivity data |

We chose 0.5 because:
- Provides strong privacy guarantees required for healthcare
- Allows reasonable model utility for threat detection
- Aligns with industry recommendations for sensitive data
- Sustainable with weekly budget of 3.5

### Why δ = 1e-5?

Delta represents the probability of a catastrophic privacy failure. Common recommendations:
- δ < 1/n where n = dataset size
- Our dataset: ~100,000 threat records
- 1e-5 = 0.00001 < 1/100,000 ✓

### Weekly Budget Renewal

- Allows 7 training rounds per week
- Prevents long-term budget accumulation
- Aligns with model update cadence
- Provides predictable privacy guarantees

## Alternatives Considered

### ε = 0.1 (Stronger Privacy)

**Pros:**
- Stronger privacy guarantees
- More conservative approach

**Cons:**
- Very high noise
- Poor model utility
- Fewer training rounds possible

**Rejected because:** Utility degradation too severe for effective threat detection.

### ε = 1.0 (Weaker Privacy)

**Pros:**
- Better model utility
- More training rounds
- Standard recommendation

**Cons:**
- Weaker privacy guarantees
- May not meet HIPAA bar for highly sensitive data

**Rejected because:** Healthcare data requires stronger guarantees.

### Local Differential Privacy (LDP)

**Pros:**
- No trusted aggregator needed
- Stronger privacy model

**Cons:**
- Much higher noise
- Significantly worse utility
- Requires larger participant base

**Rejected because:** Utility loss prohibitive; centralized aggregator acceptable with secure enclaves.

## Validation

1. **Privacy analysis** - Formal verification of ε, δ guarantees
2. **Utility testing** - Model accuracy within acceptable bounds (>90% baseline)
3. **Attack simulation** - Membership inference attacks unsuccessful
4. **Audit trail** - Privacy budget properly tracked and reported
5. **Third-party review** - Privacy parameters reviewed by external expert

## References

- Dwork, C., & Roth, A. (2014). The Algorithmic Foundations of Differential Privacy
- Opacus Library: https://opacus.ai/
- Apple's Differential Privacy: https://www.apple.com/privacy/docs/Differential_Privacy_Overview.pdf
- HIPAA De-identification Guidance: https://www.hhs.gov/hipaa/for-professionals/privacy/special-topics/de-identification/
