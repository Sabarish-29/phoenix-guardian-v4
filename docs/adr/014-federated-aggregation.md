# ADR-014: Federated Learning Aggregation Protocol

## Status
Accepted

## Date
Day 128 (Phase 3)

## Context

Phoenix Guardian's federated learning system aggregates threat intelligence from multiple hospital consortiums. The aggregation must:
1. Preserve differential privacy guarantees
2. Handle varying participant sizes
3. Tolerate participant dropouts
4. Produce useful models despite noise

## Decision

We will implement Federated Averaging (FedAvg) with secure aggregation and differential privacy.

### Protocol Flow

```
Round N:
┌────────────────────────────────────────────────────────────────┐
│ 1. Central server distributes global model M(n-1)              │
│                                                                │
│    ┌─────────────┐        Model M(n-1)                        │
│    │   Central   │ ──────────────────────►  All Participants  │
│    │   Server    │                                            │
│    └─────────────┘                                            │
│                                                                │
│ 2. Participants train locally on their data                   │
│                                                                │
│    ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐            │
│    │Hospital│  │Hospital│  │Hospital│  │Hospital│            │
│    │   A    │  │   B    │  │   C    │  │   D    │            │
│    │  Local │  │  Local │  │  Local │  │  Local │            │
│    │Training│  │Training│  │Training│  │Training│            │
│    └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘            │
│        │           │           │           │                  │
│        ▼           ▼           ▼           ▼                  │
│     ΔW_A        ΔW_B        ΔW_C        ΔW_D                 │
│                                                                │
│ 3. Apply differential privacy (clip + noise)                  │
│                                                                │
│     ΔW_A'       ΔW_B'       ΔW_C'       ΔW_D'                │
│        │           │           │           │                  │
│        └───────────┴───────────┴───────────┘                  │
│                         │                                      │
│                         ▼                                      │
│ 4. Secure aggregation at central server                       │
│                                                                │
│    ┌─────────────┐                                            │
│    │  Aggregate  │  M(n) = M(n-1) + Σ(w_i * ΔW_i') / Σ(w_i)  │
│    │   Server    │                                            │
│    └─────────────┘                                            │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import torch
from typing import List, Dict, Tuple

class FederatedAggregator:
    def __init__(
        self,
        model: torch.nn.Module,
        epsilon: float = 0.5,
        delta: float = 1e-5,
        clip_norm: float = 1.0
    ):
        self.global_model = model
        self.epsilon = epsilon
        self.delta = delta
        self.clip_norm = clip_norm
    
    def aggregate_round(
        self,
        local_updates: List[Dict[str, torch.Tensor]],
        weights: List[float],
        min_participants: int = 3
    ) -> Dict[str, torch.Tensor]:
        """
        Aggregate local model updates with differential privacy.
        """
        if len(local_updates) < min_participants:
            raise InsufficientParticipantsError(
                f"Need {min_participants} participants, got {len(local_updates)}"
            )
        
        aggregated = {}
        total_weight = sum(weights)
        
        for key in local_updates[0].keys():
            # Collect and clip updates
            clipped_updates = []
            for update in local_updates:
                delta = update[key]
                norm = torch.norm(delta)
                if norm > self.clip_norm:
                    delta = delta * (self.clip_norm / norm)
                clipped_updates.append(delta)
            
            # Weighted average
            stacked = torch.stack(clipped_updates)
            weights_tensor = torch.tensor(weights).view(-1, *[1]*(stacked.dim()-1))
            weighted_sum = (stacked * weights_tensor).sum(dim=0)
            avg_update = weighted_sum / total_weight
            
            # Add calibrated Gaussian noise
            sensitivity = 2 * self.clip_norm / len(local_updates)
            noise_scale = sensitivity * math.sqrt(2 * math.log(1.25/self.delta)) / self.epsilon
            noise = torch.randn_like(avg_update) * noise_scale
            
            aggregated[key] = avg_update + noise
        
        return aggregated
    
    def apply_update(self, aggregated_update: Dict[str, torch.Tensor]):
        """Apply aggregated update to global model."""
        with torch.no_grad():
            for name, param in self.global_model.named_parameters():
                if name in aggregated_update:
                    param.add_(aggregated_update[name])
```

## Consequences

### Positive
- Privacy preserved through differential privacy
- Works with heterogeneous data distributions
- Tolerates some participant dropout
- Improves model with each round

### Negative
- Communication overhead
- Convergence slower than centralized
- Requires minimum participant threshold
- Model quality depends on participation

## References
- McMahan et al., "Communication-Efficient Learning" (FedAvg)
- ADR-005: Differential Privacy Parameters
