#!/usr/bin/env python3
"""
Federated Model Aggregation Automation Script

This script automates the process of:
1. Collecting contributions from participating hospitals
2. Validating privacy guarantees on each contribution
3. Performing secure weighted aggregation
4. Building and publishing the global model
5. Distributing updates to all participants

Usage:
    python aggregate_federated_model.py --round round_001 --min-contributors 5
    python aggregate_federated_model.py --daemon --round-interval 86400
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from phoenix_guardian.federated.secure_aggregator import (
    SecureAggregator,
    AggregationConfig,
    AggregationResult
)
from phoenix_guardian.federated.global_model_builder import (
    GlobalModelBuilder,
    GlobalModel
)
from phoenix_guardian.federated.model_distributor import (
    ModelDistributor,
    DistributionConfig
)
from phoenix_guardian.federated.privacy_auditor import (
    PrivacyAuditor,
    AuditConfig
)
from phoenix_guardian.federated.differential_privacy import PrivacyAccountant


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FederatedAggregationOrchestrator:
    """Orchestrates the federated model aggregation process."""
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        min_contributors: int = 3,
        max_contributors: int = 100,
        round_timeout_seconds: int = 3600
    ):
        """
        Initialize the aggregation orchestrator.
        
        Args:
            config_path: Optional path to configuration file
            min_contributors: Minimum number of contributors required
            max_contributors: Maximum number of contributors allowed
            round_timeout_seconds: Timeout for collecting contributions
        """
        # Load configuration
        if config_path:
            self.config = self._load_config(config_path)
        else:
            self.config = self._default_config()
        
        # Override with explicit parameters
        self.config["min_contributors"] = min_contributors
        self.config["max_contributors"] = max_contributors
        self.config["round_timeout_seconds"] = round_timeout_seconds
        
        # Initialize components
        self.aggregator = SecureAggregator(AggregationConfig(
            min_contributors=min_contributors,
            max_contributors=max_contributors,
            round_timeout_seconds=round_timeout_seconds,
            weight_by_data_size=self.config.get("weight_by_data_size", True),
            enable_byzantine_detection=self.config.get("enable_byzantine_detection", True)
        ))
        
        self.model_builder = GlobalModelBuilder()
        
        self.distributor = ModelDistributor(DistributionConfig(
            verify_signatures=True,
            use_delta_updates=self.config.get("use_delta_updates", True)
        ))
        
        self.auditor = PrivacyAuditor(AuditConfig(
            enable_chain_integrity=True,
            anomaly_detection_enabled=True
        ))
        
        self.privacy_accountant = PrivacyAccountant(
            epsilon=self.config.get("total_epsilon", 1.0),
            delta=self.config.get("total_delta", 1e-5)
        )
        
        # Track round history
        self.round_history: List[Dict] = []
        self.current_round_id: Optional[str] = None
        
        logger.info(f"Initialized FederatedAggregationOrchestrator with {min_contributors}-{max_contributors} contributors")
    
    def _default_config(self) -> Dict:
        """Return default configuration."""
        return {
            "min_contributors": 3,
            "max_contributors": 100,
            "round_timeout_seconds": 3600,
            "weight_by_data_size": True,
            "enable_byzantine_detection": True,
            "use_delta_updates": True,
            "total_epsilon": 1.0,
            "total_delta": 1e-5,
            "model_version_prefix": "v",
            "distribution_channels": ["stable"],
            "notify_on_completion": True,
            "output_directory": "./aggregation_results"
        }
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from file."""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    async def start_round(
        self,
        round_id: Optional[str] = None,
        base_version: Optional[str] = None
    ) -> str:
        """
        Start a new aggregation round.
        
        Args:
            round_id: Optional custom round ID
            base_version: Base model version to build upon
            
        Returns:
            The round ID
        """
        if round_id is None:
            round_id = f"round_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        self.current_round_id = round_id
        
        # Determine base version
        if base_version is None:
            latest = await self.distributor.get_current_version()
            base_version = latest.version_id if latest else "v0.0.0"
        
        # Start aggregator round
        await self.aggregator.start_round(model_version=base_version)
        
        # Log to auditor
        self.auditor.log_event({
            "event_type": "round_started",
            "round_id": round_id,
            "base_version": base_version,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        logger.info(f"Started aggregation round {round_id} (base: {base_version})")
        
        return round_id
    
    async def collect_contributions(
        self,
        contributions: List[Dict]
    ) -> Tuple[int, int]:
        """
        Collect contributions from participants.
        
        Args:
            contributions: List of contribution dictionaries
            
        Returns:
            Tuple of (accepted_count, rejected_count)
        """
        if not self.current_round_id:
            raise ValueError("No active round. Call start_round first.")
        
        accepted = 0
        rejected = 0
        
        for contribution in contributions:
            try:
                # Validate contribution
                validation = await self._validate_contribution(contribution)
                
                if not validation["is_valid"]:
                    logger.warning(
                        f"Rejected contribution from {contribution['contributor_id']}: "
                        f"{validation['reason']}"
                    )
                    rejected += 1
                    continue
                
                # Submit to aggregator
                result = await self.aggregator.submit_contribution(contribution)
                
                if result["status"] == "accepted":
                    # Log to auditor
                    self.auditor.log_contribution(
                        participant_id=contribution["contributor_id"],
                        round_id=self.current_round_id,
                        epsilon_used=contribution.get("privacy_budget_used", 0),
                        delta_used=contribution.get("delta_used", 0)
                    )
                    
                    # Update privacy accountant
                    self.privacy_accountant.record_operation(
                        contribution.get("privacy_budget_used", 0),
                        contribution.get("delta_used", 0)
                    )
                    
                    accepted += 1
                else:
                    rejected += 1
                    
            except Exception as e:
                logger.error(f"Error processing contribution: {e}")
                rejected += 1
        
        logger.info(f"Collected contributions: {accepted} accepted, {rejected} rejected")
        
        return accepted, rejected
    
    async def _validate_contribution(self, contribution: Dict) -> Dict:
        """Validate a contribution meets requirements."""
        # Check required fields
        required_fields = ["contributor_id", "model_update", "data_size"]
        for field in required_fields:
            if field not in contribution:
                return {"is_valid": False, "reason": f"Missing required field: {field}"}
        
        # Check model update dimensions
        model_update = np.array(contribution["model_update"])
        if model_update.ndim == 0:
            return {"is_valid": False, "reason": "Invalid model update dimensions"}
        
        # Check for NaN or Inf values
        if np.any(np.isnan(model_update)) or np.any(np.isinf(model_update)):
            return {"is_valid": False, "reason": "Model update contains NaN or Inf values"}
        
        # Check data size is positive
        if contribution["data_size"] <= 0:
            return {"is_valid": False, "reason": "Data size must be positive"}
        
        # Check privacy budget
        privacy_used = contribution.get("privacy_budget_used", 0)
        remaining = self.privacy_accountant.get_remaining_budget()
        if privacy_used > remaining:
            return {"is_valid": False, "reason": "Insufficient privacy budget"}
        
        return {"is_valid": True}
    
    async def aggregate(self) -> AggregationResult:
        """
        Perform aggregation on collected contributions.
        
        Returns:
            AggregationResult with aggregated model
        """
        if not self.current_round_id:
            raise ValueError("No active round.")
        
        logger.info("Starting aggregation...")
        
        result = await self.aggregator.aggregate()
        
        # Log aggregation event
        self.auditor.log_aggregation(
            round_id=self.current_round_id,
            num_contributors=result.num_contributors,
            total_epsilon=result.privacy_budget_consumed,
            model_version="pending"
        )
        
        logger.info(
            f"Aggregation complete: {result.num_contributors} contributors, "
            f"total data size: {result.total_data_size}"
        )
        
        return result
    
    async def build_global_model(
        self,
        aggregation_result: AggregationResult
    ) -> GlobalModel:
        """
        Build the global model from aggregation result.
        
        Args:
            aggregation_result: Result from aggregation
            
        Returns:
            GlobalModel ready for distribution
        """
        logger.info("Building global model...")
        
        global_model = await self.model_builder.build(
            base_version=self.aggregator.current_round.model_version,
            aggregated_updates=aggregation_result.aggregated_model,
            round_id=self.current_round_id,
            metadata={
                "num_contributors": aggregation_result.num_contributors,
                "total_data_size": aggregation_result.total_data_size,
                "privacy_budget_consumed": aggregation_result.privacy_budget_consumed,
                "aggregation_time": aggregation_result.aggregation_time_seconds
            }
        )
        
        logger.info(f"Global model built: version {global_model.version_id}")
        
        return global_model
    
    async def distribute_model(
        self,
        global_model: GlobalModel,
        channels: Optional[List[str]] = None
    ) -> Dict:
        """
        Distribute the global model to participants.
        
        Args:
            global_model: GlobalModel to distribute
            channels: Distribution channels (default: from config)
            
        Returns:
            Distribution result summary
        """
        if channels is None:
            channels = self.config.get("distribution_channels", ["stable"])
        
        logger.info(f"Distributing model {global_model.version_id} to channels: {channels}")
        
        distribution_results = {}
        
        for channel in channels:
            try:
                version = await self.distributor.publish(
                    version_id=global_model.version_id,
                    model_weights=global_model.weights,
                    metadata=global_model.metadata,
                    channel=channel
                )
                
                distribution_results[channel] = {
                    "status": "success",
                    "version": version.version_id
                }
                
            except Exception as e:
                logger.error(f"Error distributing to channel {channel}: {e}")
                distribution_results[channel] = {
                    "status": "error",
                    "error": str(e)
                }
        
        logger.info(f"Distribution complete: {distribution_results}")
        
        return distribution_results
    
    async def complete_round(
        self,
        save_results: bool = True
    ) -> Dict:
        """
        Complete the current round and generate summary.
        
        Args:
            save_results: Whether to save results to disk
            
        Returns:
            Round summary dictionary
        """
        if not self.current_round_id:
            raise ValueError("No active round to complete.")
        
        # Get round summary
        summary = {
            "round_id": self.current_round_id,
            "completed_at": datetime.utcnow().isoformat(),
            "aggregator_stats": self.aggregator.get_round_stats(),
            "privacy_budget_total": self.privacy_accountant.get_total_privacy_cost(),
            "privacy_budget_remaining": self.privacy_accountant.get_remaining_budget()
        }
        
        # Generate audit report
        report = self.auditor.generate_report(
            period_start=datetime.utcnow() - timedelta(hours=24),
            period_end=datetime.utcnow()
        )
        summary["audit_report"] = report.to_dict()
        
        # Save results
        if save_results:
            output_dir = Path(self.config.get("output_directory", "./aggregation_results"))
            output_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = output_dir / f"{self.current_round_id}_summary.json"
            with open(output_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            logger.info(f"Round summary saved to {output_file}")
        
        # Add to history
        self.round_history.append(summary)
        
        # Reset for next round
        self.current_round_id = None
        
        logger.info(f"Round completed: {summary['round_id']}")
        
        return summary
    
    async def run_full_round(
        self,
        contributions: List[Dict],
        round_id: Optional[str] = None
    ) -> Dict:
        """
        Run a complete aggregation round from start to finish.
        
        Args:
            contributions: List of contributions to process
            round_id: Optional custom round ID
            
        Returns:
            Round summary
        """
        # Start round
        round_id = await self.start_round(round_id)
        
        try:
            # Collect contributions
            accepted, rejected = await self.collect_contributions(contributions)
            
            if accepted < self.config["min_contributors"]:
                raise ValueError(
                    f"Insufficient contributors: {accepted} < {self.config['min_contributors']}"
                )
            
            # Aggregate
            aggregation_result = await self.aggregate()
            
            # Build global model
            global_model = await self.build_global_model(aggregation_result)
            
            # Distribute
            distribution_results = await self.distribute_model(global_model)
            
            # Complete round
            summary = await self.complete_round()
            summary["distribution_results"] = distribution_results
            
            return summary
            
        except Exception as e:
            logger.error(f"Error in round {round_id}: {e}")
            await self.complete_round(save_results=True)
            raise
    
    def get_status(self) -> Dict:
        """Get current orchestrator status."""
        return {
            "active_round": self.current_round_id,
            "rounds_completed": len(self.round_history),
            "privacy_budget_remaining": self.privacy_accountant.get_remaining_budget(),
            "aggregator_status": self.aggregator.get_status() if hasattr(self.aggregator, 'get_status') else "unknown"
        }


async def daemon_mode(
    orchestrator: FederatedAggregationOrchestrator,
    contribution_dir: str,
    round_interval: int
) -> None:
    """
    Run in daemon mode, periodically aggregating contributions.
    
    Args:
        orchestrator: FederatedAggregationOrchestrator instance
        contribution_dir: Directory to watch for contributions
        round_interval: Interval between rounds in seconds
    """
    logger.info(f"Starting daemon mode, round interval: {round_interval} seconds")
    
    while True:
        try:
            # Collect contribution files
            contributions = []
            contribution_path = Path(contribution_dir)
            
            for json_file in contribution_path.glob("*.json"):
                try:
                    with open(json_file, 'r') as f:
                        contribution = json.load(f)
                    contributions.append(contribution)
                except Exception as e:
                    logger.error(f"Error loading contribution {json_file}: {e}")
            
            if len(contributions) >= orchestrator.config["min_contributors"]:
                logger.info(f"Found {len(contributions)} contributions, starting round")
                
                summary = await orchestrator.run_full_round(contributions)
                
                # Archive processed contributions
                archive_dir = contribution_path / "archived" / summary["round_id"]
                archive_dir.mkdir(parents=True, exist_ok=True)
                
                for json_file in contribution_path.glob("*.json"):
                    json_file.rename(archive_dir / json_file.name)
                
                logger.info(f"Round complete, archived contributions to {archive_dir}")
            else:
                logger.info(
                    f"Waiting for more contributions: "
                    f"{len(contributions)}/{orchestrator.config['min_contributors']}"
                )
            
            await asyncio.sleep(round_interval)
            
        except KeyboardInterrupt:
            logger.info("Daemon mode interrupted")
            break
        except Exception as e:
            logger.error(f"Error in daemon mode: {e}")
            await asyncio.sleep(round_interval)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Aggregate federated learning contributions"
    )
    
    parser.add_argument(
        "--round",
        help="Round ID for this aggregation"
    )
    parser.add_argument(
        "--contributions",
        help="Path to contributions JSON file or directory"
    )
    parser.add_argument(
        "--min-contributors",
        type=int,
        default=3,
        help="Minimum number of contributors required (default: 3)"
    )
    parser.add_argument(
        "--max-contributors",
        type=int,
        default=100,
        help="Maximum number of contributors (default: 100)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Round timeout in seconds (default: 3600)"
    )
    parser.add_argument(
        "--config",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--output-dir",
        default="./aggregation_results",
        help="Output directory for results"
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run in daemon mode"
    )
    parser.add_argument(
        "--contribution-dir",
        default="./incoming_contributions",
        help="Directory to watch for contributions in daemon mode"
    )
    parser.add_argument(
        "--round-interval",
        type=int,
        default=86400,
        help="Interval between rounds in daemon mode (default: 86400 = 24 hours)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize orchestrator
    orchestrator = FederatedAggregationOrchestrator(
        config_path=args.config,
        min_contributors=args.min_contributors,
        max_contributors=args.max_contributors,
        round_timeout_seconds=args.timeout
    )
    
    # Update output directory
    orchestrator.config["output_directory"] = args.output_dir
    
    if args.daemon:
        # Daemon mode
        Path(args.contribution_dir).mkdir(parents=True, exist_ok=True)
        
        await daemon_mode(
            orchestrator,
            args.contribution_dir,
            args.round_interval
        )
    else:
        # Single round mode
        if not args.contributions:
            parser.error("--contributions is required in single round mode")
        
        # Load contributions
        contributions_path = Path(args.contributions)
        
        if contributions_path.is_dir():
            contributions = []
            for json_file in contributions_path.glob("*.json"):
                with open(json_file, 'r') as f:
                    contributions.append(json.load(f))
        else:
            with open(contributions_path, 'r') as f:
                data = json.load(f)
            contributions = data if isinstance(data, list) else [data]
        
        # Run aggregation
        summary = await orchestrator.run_full_round(
            contributions,
            round_id=args.round
        )
        
        # Print summary
        print(f"\n{'='*60}")
        print("Federated Model Aggregation Complete")
        print(f"{'='*60}")
        print(f"Round ID: {summary['round_id']}")
        print(f"Contributors: {summary['aggregator_stats'].get('num_contributors', 'N/A')}")
        print(f"Total Data Size: {summary['aggregator_stats'].get('total_data_size', 'N/A')}")
        print(f"Privacy Budget Used: {summary['privacy_budget_total']}")
        print(f"Results saved to: {args.output_dir}/{summary['round_id']}_summary.json")


if __name__ == "__main__":
    asyncio.run(main())
