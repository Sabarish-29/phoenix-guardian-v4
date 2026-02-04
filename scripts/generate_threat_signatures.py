#!/usr/bin/env python3
"""
Threat Signature Generation Automation Script

This script automates the process of:
1. Collecting attack patterns from local detection systems
2. Applying differential privacy to protect sensitive data
3. Generating federated-ready threat signatures
4. Preparing contributions for the federated learning network

Usage:
    python generate_threat_signatures.py --input attacks.json --output signatures.json
    python generate_threat_signatures.py --watch --interval 3600
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from phoenix_guardian.federated.differential_privacy import (
    DifferentialPrivacyEngine,
    PrivacyBudget
)
from phoenix_guardian.federated.threat_signature import (
    ThreatSignature,
    ThreatSignatureGenerator
)
from phoenix_guardian.federated.attack_pattern_extractor import (
    AttackPatternExtractor,
    AttackPattern
)
from phoenix_guardian.federated.privacy_validator import PrivacyValidator
from phoenix_guardian.federated.contribution_pipeline import ContributionPipeline


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ThreatSignatureAutomation:
    """Automates threat signature generation with privacy preservation."""
    
    def __init__(
        self,
        epsilon: float = 0.5,
        delta: float = 1e-5,
        config_path: Optional[str] = None
    ):
        """
        Initialize the automation system.
        
        Args:
            epsilon: Privacy budget epsilon parameter
            delta: Privacy budget delta parameter
            config_path: Optional path to configuration file
        """
        self.epsilon = epsilon
        self.delta = delta
        
        # Load configuration
        if config_path:
            self.config = self._load_config(config_path)
        else:
            self.config = self._default_config()
        
        # Initialize components
        self.dp_engine = DifferentialPrivacyEngine(epsilon=epsilon, delta=delta)
        self.pattern_extractor = AttackPatternExtractor()
        self.signature_generator = ThreatSignatureGenerator()
        self.privacy_validator = PrivacyValidator()
        self.contribution_pipeline = ContributionPipeline()
        
        # Track generated signatures
        self.generated_signatures: List[ThreatSignature] = []
        self.privacy_budget_used = 0.0
        
        logger.info(f"Initialized ThreatSignatureAutomation with ε={epsilon}, δ={delta}")
    
    def _default_config(self) -> Dict:
        """Return default configuration."""
        return {
            "min_attack_confidence": 0.7,
            "max_signatures_per_batch": 100,
            "signature_vector_size": 256,
            "privacy_budget_per_signature": 0.01,
            "output_format": "json",
            "validate_before_output": True,
            "supported_attack_types": [
                "ransomware",
                "phishing",
                "malware",
                "insider_threat",
                "data_exfiltration",
                "denial_of_service",
                "sql_injection",
                "privilege_escalation"
            ]
        }
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from file."""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    async def process_attack_events(
        self,
        events: List[Dict],
        participant_id: str
    ) -> List[ThreatSignature]:
        """
        Process raw attack events into privacy-preserving signatures.
        
        Args:
            events: List of raw attack event dictionaries
            participant_id: ID of the contributing participant
            
        Returns:
            List of generated ThreatSignature objects
        """
        logger.info(f"Processing {len(events)} attack events from {participant_id}")
        
        signatures = []
        
        for event in events:
            try:
                # Validate event structure
                if not self._validate_event(event):
                    logger.warning(f"Skipping invalid event: {event.get('event_id', 'unknown')}")
                    continue
                
                # Check confidence threshold
                if event.get("confidence", 1.0) < self.config["min_attack_confidence"]:
                    logger.debug(f"Skipping low-confidence event: {event.get('event_id')}")
                    continue
                
                # Extract attack pattern
                pattern = self.pattern_extractor.extract(event)
                
                # Generate signature with differential privacy
                signature = await self._generate_private_signature(pattern, participant_id)
                
                if signature:
                    signatures.append(signature)
                    self.privacy_budget_used += self.config["privacy_budget_per_signature"]
                
                # Check batch limit
                if len(signatures) >= self.config["max_signatures_per_batch"]:
                    logger.info(f"Reached batch limit of {self.config['max_signatures_per_batch']}")
                    break
                
                # Check privacy budget
                if self.privacy_budget_used >= self.epsilon * 0.9:
                    logger.warning("Approaching privacy budget limit, stopping processing")
                    break
                    
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                continue
        
        self.generated_signatures.extend(signatures)
        logger.info(f"Generated {len(signatures)} threat signatures")
        
        return signatures
    
    def _validate_event(self, event: Dict) -> bool:
        """Validate event has required fields."""
        required_fields = ["attack_type", "timestamp"]
        return all(field in event for field in required_fields)
    
    async def _generate_private_signature(
        self,
        pattern: AttackPattern,
        participant_id: str
    ) -> Optional[ThreatSignature]:
        """Generate a differentially private threat signature."""
        try:
            # Convert pattern to feature vector
            feature_vector = pattern.to_feature_vector(
                size=self.config["signature_vector_size"]
            )
            
            # Apply differential privacy
            private_vector = self.dp_engine.add_noise(
                feature_vector,
                sensitivity=1.0,
                participant_id=participant_id
            )
            
            # Generate signature
            signature = self.signature_generator.generate(
                pattern=pattern,
                private_vector=private_vector,
                metadata={
                    "participant_id": participant_id,
                    "generated_at": datetime.utcnow().isoformat(),
                    "privacy_epsilon": self.config["privacy_budget_per_signature"]
                }
            )
            
            # Validate privacy guarantees
            if self.config["validate_before_output"]:
                validation = self.privacy_validator.validate(
                    original=feature_vector,
                    processed=private_vector,
                    epsilon=self.config["privacy_budget_per_signature"]
                )
                
                if not validation.is_valid:
                    logger.warning(f"Signature failed privacy validation")
                    return None
            
            return signature
            
        except Exception as e:
            logger.error(f"Error generating signature: {e}")
            return None
    
    async def prepare_contribution(
        self,
        participant_id: str,
        round_id: str
    ) -> Dict:
        """
        Prepare a federated learning contribution.
        
        Args:
            participant_id: ID of the contributing participant
            round_id: Current federated learning round ID
            
        Returns:
            Contribution dictionary ready for submission
        """
        if not self.generated_signatures:
            raise ValueError("No signatures generated to contribute")
        
        # Combine signatures into contribution
        contribution_vector = self._combine_signatures(self.generated_signatures)
        
        contribution = {
            "contributor_id": participant_id,
            "round_id": round_id,
            "model_update": contribution_vector.tolist(),
            "data_size": len(self.generated_signatures),
            "privacy_budget_used": self.privacy_budget_used,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "attack_types": list(set(
                    s.attack_type for s in self.generated_signatures
                )),
                "severity_distribution": self._get_severity_distribution()
            }
        }
        
        logger.info(f"Prepared contribution with {len(self.generated_signatures)} signatures")
        
        return contribution
    
    def _combine_signatures(self, signatures: List[ThreatSignature]) -> np.ndarray:
        """Combine multiple signatures into a single vector."""
        vectors = [s.to_vector() for s in signatures]
        return np.mean(vectors, axis=0)
    
    def _get_severity_distribution(self) -> Dict[str, int]:
        """Get distribution of severities in generated signatures."""
        distribution = {}
        for sig in self.generated_signatures:
            severity = sig.severity
            distribution[severity] = distribution.get(severity, 0) + 1
        return distribution
    
    def export_signatures(
        self,
        output_path: str,
        format: str = "json"
    ) -> None:
        """
        Export generated signatures to file.
        
        Args:
            output_path: Path to output file
            format: Output format (json, csv)
        """
        if format == "json":
            self._export_json(output_path)
        elif format == "csv":
            self._export_csv(output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"Exported {len(self.generated_signatures)} signatures to {output_path}")
    
    def _export_json(self, output_path: str) -> None:
        """Export signatures as JSON."""
        data = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_signatures": len(self.generated_signatures),
            "privacy_budget_used": self.privacy_budget_used,
            "signatures": [s.to_dict() for s in self.generated_signatures]
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _export_csv(self, output_path: str) -> None:
        """Export signatures as CSV."""
        import csv
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'signature_id', 'attack_type', 'severity', 
                'confidence', 'generated_at'
            ])
            writer.writeheader()
            
            for sig in self.generated_signatures:
                writer.writerow({
                    'signature_id': sig.signature_id,
                    'attack_type': sig.attack_type,
                    'severity': sig.severity,
                    'confidence': sig.confidence,
                    'generated_at': sig.generated_at
                })
    
    def get_status(self) -> Dict:
        """Get current status of the automation system."""
        return {
            "signatures_generated": len(self.generated_signatures),
            "privacy_budget_total": self.epsilon,
            "privacy_budget_used": self.privacy_budget_used,
            "privacy_budget_remaining": self.epsilon - self.privacy_budget_used,
            "dp_engine_status": self.dp_engine.get_status()
        }
    
    def reset(self) -> None:
        """Reset the automation system for a new batch."""
        self.generated_signatures = []
        self.privacy_budget_used = 0.0
        logger.info("Reset automation system")


async def watch_mode(
    automation: ThreatSignatureAutomation,
    input_dir: str,
    output_dir: str,
    interval: int,
    participant_id: str
) -> None:
    """
    Run in watch mode, continuously processing new attack events.
    
    Args:
        automation: ThreatSignatureAutomation instance
        input_dir: Directory to watch for input files
        output_dir: Directory for output files
        interval: Polling interval in seconds
        participant_id: Participant ID for contributions
    """
    logger.info(f"Starting watch mode, polling every {interval} seconds")
    
    processed_files = set()
    
    while True:
        try:
            input_path = Path(input_dir)
            
            # Find new JSON files
            for json_file in input_path.glob("*.json"):
                if str(json_file) in processed_files:
                    continue
                
                logger.info(f"Processing new file: {json_file}")
                
                # Load events
                with open(json_file, 'r') as f:
                    events = json.load(f)
                
                if isinstance(events, dict):
                    events = events.get("events", [events])
                
                # Process events
                await automation.process_attack_events(events, participant_id)
                
                # Export signatures
                output_file = Path(output_dir) / f"signatures_{json_file.stem}.json"
                automation.export_signatures(str(output_file))
                
                processed_files.add(str(json_file))
                automation.reset()
            
            await asyncio.sleep(interval)
            
        except KeyboardInterrupt:
            logger.info("Watch mode interrupted")
            break
        except Exception as e:
            logger.error(f"Error in watch mode: {e}")
            await asyncio.sleep(interval)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate privacy-preserving threat signatures"
    )
    
    parser.add_argument(
        "--input", "-i",
        help="Input file with attack events (JSON)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file for signatures"
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=0.5,
        help="Privacy budget epsilon (default: 0.5)"
    )
    parser.add_argument(
        "--delta",
        type=float,
        default=1e-5,
        help="Privacy budget delta (default: 1e-5)"
    )
    parser.add_argument(
        "--participant-id",
        default="local_hospital",
        help="Participant ID for contributions"
    )
    parser.add_argument(
        "--config",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run in watch mode"
    )
    parser.add_argument(
        "--watch-input-dir",
        default="./incoming_attacks",
        help="Directory to watch for input files"
    )
    parser.add_argument(
        "--watch-output-dir",
        default="./generated_signatures",
        help="Directory for output files"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Watch mode polling interval in seconds (default: 3600)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize automation
    automation = ThreatSignatureAutomation(
        epsilon=args.epsilon,
        delta=args.delta,
        config_path=args.config
    )
    
    if args.watch:
        # Watch mode
        Path(args.watch_input_dir).mkdir(parents=True, exist_ok=True)
        Path(args.watch_output_dir).mkdir(parents=True, exist_ok=True)
        
        await watch_mode(
            automation,
            args.watch_input_dir,
            args.watch_output_dir,
            args.interval,
            args.participant_id
        )
    else:
        # Single file mode
        if not args.input or not args.output:
            parser.error("--input and --output are required in single file mode")
        
        # Load events
        with open(args.input, 'r') as f:
            data = json.load(f)
        
        events = data if isinstance(data, list) else data.get("events", [data])
        
        # Process events
        signatures = await automation.process_attack_events(
            events,
            args.participant_id
        )
        
        # Export
        automation.export_signatures(args.output)
        
        # Print summary
        status = automation.get_status()
        print(f"\n{'='*50}")
        print(f"Threat Signature Generation Complete")
        print(f"{'='*50}")
        print(f"Signatures generated: {status['signatures_generated']}")
        print(f"Privacy budget used: {status['privacy_budget_used']:.4f}")
        print(f"Privacy budget remaining: {status['privacy_budget_remaining']:.4f}")
        print(f"Output saved to: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
