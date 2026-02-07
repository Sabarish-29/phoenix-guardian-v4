"""
Agent Orchestration Layer.

Coordinates all 10 Phoenix Guardian AI agents through a unified interface
with parallel execution, dependency management, and health monitoring.

Agents:
 1. ScribeAgent     — SOAP note generation
 2. SafetyAgent     — Drug interaction checking
 3. NavigatorAgent   — Workflow suggestions
 4. CodingAgent     — ICD-10/CPT code suggestion
 5. SentinelAgent   — Security threat detection
 6. OrderManagement — Lab/imaging/prescription orders
 7. DeceptionDetection — Clinical consistency analysis
 8. FraudAgent      — Billing fraud detection
 9. ClinicalDecision — Evidence-based decision support
10. PharmacyAgent   — Formulary & e-prescribing

Architecture:
    ┌────────────────────────────────────────────────┐
    │           AgentOrchestrator                    │
    │                                                │
    │  ┌─────────┐ ┌──────────┐ ┌─────────────────┐ │
    │  │ Scribe  │ │  Safety  │ │  Sentinel       │ │
    │  └────┬────┘ └────┬─────┘ └───────┬─────────┘ │
    │       │           │               │            │
    │  ┌────▼────┐ ┌────▼─────┐ ┌───────▼─────────┐ │
    │  │ Coding  │ │ Pharmacy │ │ ClinicalDecision│ │
    │  └────┬────┘ └────┬─────┘ └───────┬─────────┘ │
    │       │           │               │            │
    │  ┌────▼────┐ ┌────▼─────┐ ┌───────▼─────────┐ │
    │  │ Fraud   │ │ Orders   │ │ Deception       │ │
    │  └─────────┘ └──────────┘ └─────────────────┘ │
    │                                                │
    │           ┌──────────┐                         │
    │           │Navigator │ (workflow coordination) │
    │           └──────────┘                         │
    └────────────────────────────────────────────────┘

Execution Strategy:
- Phase 1 (parallel): Scribe + Sentinel + Safety
- Phase 2 (parallel): Coding + ClinicalDecision + Deception
- Phase 3 (parallel): Fraud + Orders + Pharmacy
- Phase 4: Navigator (post-processing workflow)

Sprint 6, Days 11-12: Agent Orchestration Layer
"""

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class AgentStatus(str, Enum):
    """Status of an individual agent."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    INITIALIZING = "initializing"


@dataclass
class AgentInfo:
    """Information about a registered agent."""
    name: str
    agent_class: str
    status: AgentStatus = AgentStatus.INITIALIZING
    version: str = "1.0.0"
    total_calls: int = 0
    total_errors: int = 0
    avg_latency_ms: float = 0.0
    last_called: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class OrchestrationResult:
    """Result from a full agent orchestration run."""
    id: str
    status: str
    total_time_ms: float
    agents_called: int
    agents_succeeded: int
    agents_failed: int
    results: Dict[str, Any]
    errors: Dict[str, str]
    phases_executed: int
    created_at: str


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════


class AgentOrchestrator:
    """
    Orchestrates all 10 Phoenix Guardian agents.
    
    Features:
    - Parallel execution within phases
    - Dependency-aware scheduling
    - Health monitoring and circuit breaking
    - Graceful degradation (skip failed non-critical agents)
    - Comprehensive metrics tracking
    - Configurable execution phases
    
    Execution Phases:
    1. Critical Safety Gate: Sentinel (security), Safety (drug interactions)
    2. Core Processing: Scribe (SOAP), Coding (ICD/CPT), ClinicalDecision
    3. Supplementary: Fraud, Orders, Pharmacy, Deception
    4. Coordination: Navigator (workflow)
    
    Usage:
        orchestrator = AgentOrchestrator()
        result = await orchestrator.process_encounter({
            "patient_mrn": "MRN001",
            "transcript": "...",
            "symptoms": [...],
            "medications": [...],
        })
    """
    
    # Define execution phases with agent groups
    EXECUTION_PHASES = [
        {
            "name": "safety_gate",
            "agents": ["sentinel", "safety"],
            "critical": True,  # Abort if any fails
            "description": "Security and drug safety checks",
        },
        {
            "name": "core_processing",
            "agents": ["scribe", "coding", "clinical_decision"],
            "critical": False,
            "description": "SOAP generation, coding, clinical decisions",
        },
        {
            "name": "supplementary",
            "agents": ["fraud", "orders", "pharmacy", "deception"],
            "critical": False,
            "description": "Fraud detection, orders, pharmacy, consistency",
        },
        {
            "name": "coordination",
            "agents": ["navigator"],
            "critical": False,
            "description": "Workflow coordination and next steps",
        },
    ]
    
    def __init__(self, timeout_per_agent: float = 30.0):
        """
        Initialize the agent orchestrator.
        
        Args:
            timeout_per_agent: Maximum seconds to wait for each agent.
        """
        self.timeout = timeout_per_agent
        self._agents: Dict[str, AgentInfo] = {}
        self._agent_instances: Dict[str, Any] = {}
        self._circuit_breaker: Dict[str, int] = {}  # error count per agent
        self._circuit_threshold = 5  # errors before circuit opens
        
        # Register all agents
        self._register_agents()
    
    def _register_agents(self) -> None:
        """Register all 10 agents with their metadata."""
        agent_registry = [
            AgentInfo(
                name="scribe",
                agent_class="ScribeAgent",
                capabilities=["soap_generation", "icd_extraction"],
                dependencies=[],
            ),
            AgentInfo(
                name="safety",
                agent_class="SafetyAgent",
                capabilities=["drug_interaction_check", "allergy_check"],
                dependencies=[],
            ),
            AgentInfo(
                name="navigator",
                agent_class="NavigatorAgent",
                capabilities=["workflow_suggestion", "next_steps"],
                dependencies=["scribe"],
            ),
            AgentInfo(
                name="coding",
                agent_class="CodingAgent",
                capabilities=["icd10_suggestion", "cpt_suggestion"],
                dependencies=["scribe"],
            ),
            AgentInfo(
                name="sentinel",
                agent_class="SentinelAgent",
                capabilities=["threat_detection", "anomaly_detection"],
                dependencies=[],
            ),
            AgentInfo(
                name="orders",
                agent_class="OrderManagementAgent",
                capabilities=["lab_suggestion", "imaging_suggestion", "prescription"],
                dependencies=[],
            ),
            AgentInfo(
                name="deception",
                agent_class="DeceptionDetectionAgent",
                capabilities=["consistency_analysis", "drug_seeking_detection"],
                dependencies=[],
            ),
            AgentInfo(
                name="fraud",
                agent_class="FraudAgent",
                capabilities=["unbundling_detection", "upcoding_detection"],
                dependencies=["coding"],
            ),
            AgentInfo(
                name="clinical_decision",
                agent_class="ClinicalDecisionAgent",
                capabilities=["risk_scores", "treatment_recommendation", "differential"],
                dependencies=[],
            ),
            AgentInfo(
                name="pharmacy",
                agent_class="PharmacyAgent",
                capabilities=["formulary_check", "prior_auth", "e_prescribing", "dur"],
                dependencies=[],
            ),
        ]
        
        for info in agent_registry:
            self._agents[info.name] = info
            self._circuit_breaker[info.name] = 0
    
    def _get_agent_instance(self, name: str) -> Any:
        """Get or create an agent instance."""
        if name not in self._agent_instances:
            try:
                agent = self._create_agent(name)
                self._agent_instances[name] = agent
                self._agents[name].status = AgentStatus.HEALTHY
            except Exception as e:
                logger.error(f"Failed to create agent '{name}': {e}")
                self._agents[name].status = AgentStatus.UNAVAILABLE
                return None
        return self._agent_instances[name]
    
    def _create_agent(self, name: str) -> Any:
        """Create an agent instance by name."""
        from phoenix_guardian.agents.scribe import ScribeAgent
        from phoenix_guardian.agents.safety import SafetyAgent
        from phoenix_guardian.agents.navigator import NavigatorAgent
        from phoenix_guardian.agents.coding import CodingAgent
        from phoenix_guardian.agents.sentinel import SentinelAgent
        from phoenix_guardian.agents.order_management import OrderManagementAgent
        from phoenix_guardian.agents.deception_detection import DeceptionDetectionAgent
        from phoenix_guardian.agents.fraud import FraudAgent
        from phoenix_guardian.agents.clinical_decision import ClinicalDecisionAgent
        from phoenix_guardian.agents.pharmacy import PharmacyAgent
        
        agent_map = {
            "scribe": ScribeAgent,
            "safety": SafetyAgent,
            "navigator": NavigatorAgent,
            "coding": CodingAgent,
            "sentinel": SentinelAgent,
            "orders": OrderManagementAgent,
            "deception": DeceptionDetectionAgent,
            "fraud": FraudAgent,
            "clinical_decision": ClinicalDecisionAgent,
            "pharmacy": PharmacyAgent,
        }
        
        cls = agent_map.get(name)
        if cls is None:
            raise ValueError(f"Unknown agent: {name}")
        return cls()
    
    async def process_encounter(
        self,
        encounter_data: Dict[str, Any],
        agents: Optional[List[str]] = None,
        skip_agents: Optional[List[str]] = None,
    ) -> OrchestrationResult:
        """
        Process an encounter through all agents.
        
        Args:
            encounter_data: Encounter data dict with patient info, transcript, etc.
            agents: Optional list of specific agents to run (default: all).
            skip_agents: Optional list of agents to skip.
        
        Returns:
            OrchestrationResult with results from all agents.
        """
        orchestration_id = str(uuid.uuid4())
        start = time.time()
        results: Dict[str, Any] = {}
        errors: Dict[str, str] = {}
        agents_called = 0
        agents_succeeded = 0
        agents_failed = 0
        phases_executed = 0
        
        skip_set = set(skip_agents or [])
        include_set = set(agents) if agents else None
        
        logger.info(f"Orchestration {orchestration_id}: Starting encounter processing")
        
        for phase in self.EXECUTION_PHASES:
            phase_name = phase["name"]
            phase_agents = phase["agents"]
            is_critical = phase["critical"]
            
            # Filter agents for this phase
            phase_agents_filtered = [
                a for a in phase_agents
                if a not in skip_set
                and (include_set is None or a in include_set)
                and not self._is_circuit_open(a)
            ]
            
            if not phase_agents_filtered:
                continue
            
            logger.info(
                f"Orchestration {orchestration_id}: "
                f"Phase '{phase_name}' — running {phase_agents_filtered}"
            )
            
            # Execute phase agents in parallel
            phase_tasks = []
            for agent_name in phase_agents_filtered:
                task = self._run_agent(
                    agent_name, encounter_data, results, orchestration_id
                )
                phase_tasks.append((agent_name, task))
            
            # Gather results
            phase_results = await asyncio.gather(
                *[task for _, task in phase_tasks],
                return_exceptions=True,
            )
            
            for (agent_name, _), result in zip(phase_tasks, phase_results):
                agents_called += 1
                
                if isinstance(result, Exception):
                    agents_failed += 1
                    errors[agent_name] = str(result)
                    self._record_error(agent_name)
                    
                    if is_critical:
                        elapsed = (time.time() - start) * 1000
                        logger.error(
                            f"Critical agent '{agent_name}' failed in phase "
                            f"'{phase_name}' — aborting orchestration"
                        )
                        return OrchestrationResult(
                            id=orchestration_id,
                            status="aborted",
                            total_time_ms=round(elapsed, 2),
                            agents_called=agents_called,
                            agents_succeeded=agents_succeeded,
                            agents_failed=agents_failed,
                            results=results,
                            errors=errors,
                            phases_executed=phases_executed,
                            created_at=datetime.now(timezone.utc).isoformat(),
                        )
                else:
                    agents_succeeded += 1
                    results[agent_name] = result
                    self._record_success(agent_name, result)
            
            phases_executed += 1
        
        elapsed = (time.time() - start) * 1000
        
        logger.info(
            f"Orchestration {orchestration_id}: Completed in {elapsed:.0f}ms — "
            f"{agents_succeeded}/{agents_called} agents succeeded"
        )
        
        return OrchestrationResult(
            id=orchestration_id,
            status="completed" if agents_failed == 0 else "partial",
            total_time_ms=round(elapsed, 2),
            agents_called=agents_called,
            agents_succeeded=agents_succeeded,
            agents_failed=agents_failed,
            results=results,
            errors=errors,
            phases_executed=phases_executed,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    
    async def _run_agent(
        self,
        agent_name: str,
        encounter_data: Dict[str, Any],
        previous_results: Dict[str, Any],
        orchestration_id: str,
    ) -> Any:
        """Run a single agent with timeout and error handling."""
        agent = self._get_agent_instance(agent_name)
        if agent is None:
            raise RuntimeError(f"Agent '{agent_name}' is unavailable")
        
        # Build agent-specific input
        agent_input = self._build_agent_input(
            agent_name, encounter_data, previous_results
        )
        
        start = time.time()
        try:
            result = await asyncio.wait_for(
                agent.process(**agent_input),
                timeout=self.timeout,
            )
            elapsed = (time.time() - start) * 1000
            logger.info(f"Agent '{agent_name}' completed in {elapsed:.0f}ms")
            return result
        except asyncio.TimeoutError:
            raise RuntimeError(f"Agent '{agent_name}' timed out after {self.timeout}s")
        except Exception as e:
            raise RuntimeError(f"Agent '{agent_name}' failed: {str(e)}")
    
    def _build_agent_input(
        self,
        agent_name: str,
        encounter_data: Dict[str, Any],
        previous_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build agent-specific input from encounter data and previous results."""
        transcript = encounter_data.get("transcript", "")
        chief_complaint = encounter_data.get("chief_complaint", "")
        symptoms = encounter_data.get("symptoms", [])
        medications = encounter_data.get("medications", [])
        vitals = encounter_data.get("vitals", {})
        
        if agent_name == "scribe":
            return {
                "chief_complaint": chief_complaint or transcript[:200],
                "symptoms": symptoms,
                "vitals": vitals,
                "exam_findings": encounter_data.get("exam_findings", ""),
            }
        elif agent_name == "safety":
            return {"medications": medications}
        elif agent_name == "sentinel":
            return {"text": transcript}
        elif agent_name == "coding":
            soap = previous_results.get("scribe", {}).get("soap_note", transcript)
            return {"clinical_note": soap}
        elif agent_name == "navigator":
            return {
                "current_status": encounter_data.get("status", "in_progress"),
                "encounter_type": encounter_data.get("encounter_type", "General"),
            }
        elif agent_name == "orders":
            return {
                "diagnosis": encounter_data.get("diagnosis", ""),
                "chief_complaint": chief_complaint,
                "symptoms": symptoms,
            }
        elif agent_name == "deception":
            return {
                "transcript": transcript,
                "patient_history": encounter_data.get("patient_history", ""),
            }
        elif agent_name == "fraud":
            codes = previous_results.get("coding", {})
            return {
                "procedure_codes": codes.get("cpt_codes", []),
                "billed_cpt_code": encounter_data.get("billed_cpt_code", "99213"),
                "encounter_duration": encounter_data.get("duration", 15),
            }
        elif agent_name == "clinical_decision":
            return {
                "chief_complaint": chief_complaint,
                "symptoms": symptoms,
                "vitals": vitals,
                "patient_age": encounter_data.get("patient_age", 0),
            }
        elif agent_name == "pharmacy":
            return {"medications": medications}
        
        return {"text": transcript}
    
    def _is_circuit_open(self, agent_name: str) -> bool:
        """Check if circuit breaker is open for an agent."""
        return self._circuit_breaker.get(agent_name, 0) >= self._circuit_threshold
    
    def _record_error(self, agent_name: str) -> None:
        """Record an agent error (increments circuit breaker counter)."""
        self._circuit_breaker[agent_name] = self._circuit_breaker.get(agent_name, 0) + 1
        info = self._agents.get(agent_name)
        if info:
            info.total_errors += 1
            if self._is_circuit_open(agent_name):
                info.status = AgentStatus.UNAVAILABLE
                logger.warning(f"Circuit breaker OPEN for agent '{agent_name}'")
    
    def _record_success(self, agent_name: str, result: Any) -> None:
        """Record a successful agent call."""
        # Reset circuit breaker on success
        self._circuit_breaker[agent_name] = 0
        info = self._agents.get(agent_name)
        if info:
            info.total_calls += 1
            info.last_called = datetime.now(timezone.utc).isoformat()
            info.status = AgentStatus.HEALTHY
    
    def reset_circuit_breaker(self, agent_name: str) -> None:
        """Manually reset circuit breaker for an agent."""
        self._circuit_breaker[agent_name] = 0
        if agent_name in self._agents:
            self._agents[agent_name].status = AgentStatus.HEALTHY
        logger.info(f"Circuit breaker reset for agent '{agent_name}'")
    
    def get_agent_health(self) -> Dict[str, Any]:
        """Get health status of all agents."""
        return {
            name: {
                "status": info.status.value,
                "agent_class": info.agent_class,
                "total_calls": info.total_calls,
                "total_errors": info.total_errors,
                "error_rate": round(
                    info.total_errors / max(info.total_calls, 1), 3
                ),
                "capabilities": info.capabilities,
                "circuit_breaker_errors": self._circuit_breaker.get(name, 0),
                "circuit_open": self._is_circuit_open(name),
                "last_called": info.last_called,
            }
            for name, info in self._agents.items()
        }
    
    def get_agent_list(self) -> List[Dict[str, Any]]:
        """Get list of all registered agents."""
        return [
            {
                "name": info.name,
                "class": info.agent_class,
                "status": info.status.value,
                "capabilities": info.capabilities,
                "dependencies": info.dependencies,
            }
            for info in self._agents.values()
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_global_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """Get or create the global agent orchestrator."""
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = AgentOrchestrator()
    return _global_orchestrator
