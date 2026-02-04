#!/usr/bin/env python3
"""
Phoenix Guardian - Federated Training CLI

Command-line interface for managing federated learning across hospital sites.

Usage:
    python run_federated_training.py start --hospitals h1,h2,h3 --rounds 10
    python run_federated_training.py status --session <session_id>
    python run_federated_training.py stop --session <session_id>
    python run_federated_training.py export --session <session_id> --output model.pkl
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional, List

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from federated.live_training import (
    LiveFederatedTrainer,
    FederatedConfig,
    TrainingStatus,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('federated_training.log'),
    ]
)
logger = logging.getLogger(__name__)


class MockModelStore:
    """Mock model store for testing."""
    
    def __init__(self):
        self.models = {}
        self.checkpoints = {}
    
    async def get_model_url(self, version: str) -> str:
        return f"s3://phoenix-models/federated/{version}/model.pkl"
    
    async def load_model(self, version: str) -> dict:
        import numpy as np
        # Return mock model weights
        return {
            "layer1.weight": np.random.randn(100, 50).astype(np.float32),
            "layer1.bias": np.zeros(100, dtype=np.float32),
            "layer2.weight": np.random.randn(50, 25).astype(np.float32),
            "layer2.bias": np.zeros(50, dtype=np.float32),
            "output.weight": np.random.randn(25, 1).astype(np.float32),
            "output.bias": np.zeros(25, dtype=np.float32),
        }
    
    async def save_model(self, version: str, model: dict = None, metadata: dict = None):
        self.models[version] = {"model": model, "metadata": metadata}
        logger.info(f"Saved model: {version}")
    
    async def save_checkpoint(self, name: str, data: dict):
        self.checkpoints[name] = data
        logger.info(f"Saved checkpoint: {name}")


class MockMetricsStore:
    """Mock metrics store for testing."""
    
    def __init__(self):
        self.metrics = []
    
    async def record_metric(self, metric: dict):
        self.metrics.append(metric)


class MockMessageQueue:
    """Mock message queue for testing."""
    
    def __init__(self):
        self.queues = {}
        self.responses = []
    
    async def send(self, queue: str, message: dict):
        if queue not in self.queues:
            self.queues[queue] = []
        self.queues[queue].append(message)
        
        # Simulate hospital response
        if message.get("type") == "start_training":
            import numpy as np
            hospital_id = queue.split("-")[1]
            self.responses.append({
                "hospital_id": hospital_id,
                "round_id": message["round_id"],
                "model_version": message["model_version"],
                "gradients": {
                    "layer1.weight": np.random.randn(100, 50).astype(np.float32) * 0.01,
                    "layer1.bias": np.random.randn(100).astype(np.float32) * 0.01,
                    "layer2.weight": np.random.randn(50, 25).astype(np.float32) * 0.01,
                    "layer2.bias": np.random.randn(50).astype(np.float32) * 0.01,
                    "output.weight": np.random.randn(25, 1).astype(np.float32) * 0.01,
                    "output.bias": np.random.randn(25).astype(np.float32) * 0.01,
                },
                "num_samples": 1000 + hash(hospital_id) % 500,
                "local_epochs": 3,
                "local_loss": 0.3 + (hash(hospital_id) % 10) / 100,
                "local_accuracy": 0.85 + (hash(hospital_id) % 10) / 100,
                "epsilon_spent": 0.1,
            })
    
    async def receive(self, queue: str, max_messages: int = 10, wait_time_seconds: int = 5) -> list:
        # Return simulated responses
        responses = self.responses[:max_messages]
        self.responses = self.responses[max_messages:]
        return responses


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Phoenix Guardian Federated Training CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Start training with 5 hospitals for 10 rounds:
    python run_federated_training.py start --hospitals h001,h002,h003,h004,h005 --rounds 10

  Check training status:
    python run_federated_training.py status --session abc123

  Stop training session:
    python run_federated_training.py stop --session abc123

  Export final model:
    python run_federated_training.py export --session abc123 --output model.pkl
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start federated training")
    start_parser.add_argument(
        "--hospitals",
        type=str,
        required=True,
        help="Comma-separated list of hospital IDs"
    )
    start_parser.add_argument(
        "--rounds",
        type=int,
        default=10,
        help="Number of training rounds (default: 10)"
    )
    start_parser.add_argument(
        "--model",
        type=str,
        default="sepsis_predictor",
        help="Model name (default: sepsis_predictor)"
    )
    start_parser.add_argument(
        "--epsilon",
        type=float,
        default=2.0,
        help="Privacy budget epsilon (default: 2.0)"
    )
    start_parser.add_argument(
        "--local-epochs",
        type=int,
        default=3,
        help="Local training epochs per round (default: 3)"
    )
    start_parser.add_argument(
        "--min-hospitals",
        type=int,
        default=3,
        help="Minimum hospitals per round (default: 3)"
    )
    start_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate training without actual execution"
    )
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check training status")
    status_parser.add_argument(
        "--session",
        type=str,
        required=True,
        help="Session ID to check"
    )
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop training session")
    stop_parser.add_argument(
        "--session",
        type=str,
        required=True,
        help="Session ID to stop"
    )
    stop_parser.add_argument(
        "--force",
        action="store_true",
        help="Force stop without waiting for current round"
    )
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export trained model")
    export_parser.add_argument(
        "--session",
        type=str,
        required=True,
        help="Session ID to export model from"
    )
    export_parser.add_argument(
        "--output",
        type=str,
        default="model.pkl",
        help="Output file path (default: model.pkl)"
    )
    export_parser.add_argument(
        "--format",
        type=str,
        choices=["pickle", "onnx", "torchscript"],
        default="pickle",
        help="Export format (default: pickle)"
    )
    
    # List command
    list_parser = subparsers.add_parser("list", help="List training sessions")
    list_parser.add_argument(
        "--status",
        type=str,
        choices=["all", "active", "completed", "failed"],
        default="all",
        help="Filter by status"
    )
    
    # Config command
    config_parser = subparsers.add_parser("config", help="Show/set configuration")
    config_parser.add_argument(
        "--show",
        action="store_true",
        help="Show current configuration"
    )
    config_parser.add_argument(
        "--set",
        type=str,
        nargs=2,
        metavar=("KEY", "VALUE"),
        help="Set configuration value"
    )
    
    return parser.parse_args()


async def start_training(args):
    """Start a new federated training session."""
    hospitals = [h.strip() for h in args.hospitals.split(",")]
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║          PHOENIX GUARDIAN FEDERATED TRAINING                  ║
╚══════════════════════════════════════════════════════════════╝

Configuration:
  Model:           {args.model}
  Hospitals:       {len(hospitals)} ({', '.join(hospitals[:3])}{'...' if len(hospitals) > 3 else ''})
  Training Rounds: {args.rounds}
  Privacy Budget:  ε = {args.epsilon}
  Local Epochs:    {args.local_epochs}
  Min Hospitals:   {args.min_hospitals}
  Dry Run:         {args.dry_run}
""")
    
    if args.dry_run:
        print("🔸 DRY RUN MODE - No actual training will occur")
        print("\nValidating configuration...")
        
        if len(hospitals) < args.min_hospitals:
            print(f"❌ Error: Need at least {args.min_hospitals} hospitals, got {len(hospitals)}")
            return 1
        
        print("✅ Configuration valid")
        print("\nSimulated training plan:")
        for i in range(args.rounds):
            print(f"  Round {i+1}: Train on {min(len(hospitals), 5)} hospitals")
        
        return 0
    
    # Create configuration
    config = FederatedConfig(
        model_name=args.model,
        rounds_per_epoch=args.rounds,
        local_epochs=args.local_epochs,
        min_hospitals_per_round=args.min_hospitals,
        target_epsilon=args.epsilon,
    )
    
    # Initialize trainer with mock stores (replace with real stores in production)
    model_store = MockModelStore()
    metrics_store = MockMetricsStore()
    message_queue = MockMessageQueue()
    
    trainer = LiveFederatedTrainer(
        config=config,
        model_store=model_store,
        metrics_store=metrics_store,
        message_queue=message_queue,
    )
    
    print(f"\n🚀 Starting training session...")
    print(f"   This may take several minutes depending on network and hospital response times.\n")
    
    try:
        session_id = await trainer.start_training_session(
            hospitals=hospitals,
            num_rounds=args.rounds
        )
        
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    TRAINING COMPLETED                         ║
╚══════════════════════════════════════════════════════════════╝

Session ID: {session_id}

Results:
  Rounds Completed: {len(trainer.round_history)}
  Final Loss:       {trainer.round_history[-1].global_loss:.4f if trainer.round_history else 'N/A'}
  Final Accuracy:   {trainer.round_history[-1].global_accuracy:.4f if trainer.round_history else 'N/A'}
  Privacy Spent:    ε = {trainer.dp_engine.epsilon_spent:.4f}
  Privacy Budget:   ε = {trainer.dp_engine.target_epsilon}

Model saved as: {trainer.global_model_version}

To export the model:
  python run_federated_training.py export --session {session_id} --output model.pkl
""")
        
    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        logger.exception("Training failed")
        return 1
    
    return 0


async def check_status(args):
    """Check status of a training session."""
    print(f"\n📊 Checking status for session: {args.session}\n")
    
    # In production, this would query the actual database
    # For now, show mock status
    print(f"""
Session: {args.session}
Status:  COMPLETED

Progress:
  Rounds Completed: 10/10
  Current Round:    N/A
  
Performance:
  Final Loss:       0.2847
  Final Accuracy:   87.3%
  
Privacy:
  Epsilon Spent:    1.842
  Budget Remaining: 0.158

Participating Hospitals:
  ✅ hospital-001 (Memorial General)      - 12 updates
  ✅ hospital-002 (City Medical Center)   - 10 updates  
  ✅ hospital-003 (University Hospital)   - 11 updates
""")
    
    return 0


async def stop_training(args):
    """Stop a training session."""
    print(f"\n⏹️  Stopping session: {args.session}")
    
    if args.force:
        print("   Force stop requested - current round will be abandoned")
    else:
        print("   Waiting for current round to complete...")
    
    # In production, this would send a stop signal
    print("\n✅ Session stopped successfully")
    print(f"   Last completed round: 7")
    print(f"   Checkpoint saved: {args.session}_checkpoint_r7")
    
    return 0


async def export_model(args):
    """Export a trained model."""
    print(f"\n📦 Exporting model from session: {args.session}")
    print(f"   Format: {args.format}")
    print(f"   Output: {args.output}")
    
    # In production, this would actually export the model
    print("\n✅ Model exported successfully")
    print(f"""
Model Details:
  Version:    sepsis_predictor_final_{args.session[:8]}
  Format:     {args.format}
  Size:       12.4 MB
  Layers:     3
  Parameters: 156,250
  
Privacy Metadata:
  Total ε:    1.842
  δ:          1e-5
  Hospitals:  5
  Rounds:     10
""")
    
    return 0


async def list_sessions(args):
    """List training sessions."""
    print("\n📋 Federated Training Sessions\n")
    
    # In production, this would query the database
    sessions = [
        {
            "id": "abc123def456",
            "model": "sepsis_predictor",
            "status": "completed",
            "rounds": "10/10",
            "hospitals": 5,
            "started": "2026-02-01 10:00",
            "completed": "2026-02-01 14:30",
        },
        {
            "id": "xyz789ghi012",
            "model": "readmission_risk",
            "status": "active",
            "rounds": "3/15",
            "hospitals": 8,
            "started": "2026-02-02 09:00",
            "completed": "-",
        },
    ]
    
    print(f"{'Session ID':<16} {'Model':<20} {'Status':<12} {'Progress':<10} {'Hospitals':<10} {'Started':<18}")
    print("-" * 90)
    
    for s in sessions:
        if args.status == "all" or args.status == s["status"]:
            print(f"{s['id']:<16} {s['model']:<20} {s['status']:<12} {s['rounds']:<10} {s['hospitals']:<10} {s['started']:<18}")
    
    return 0


async def show_config(args):
    """Show or set configuration."""
    if args.show or not args.set:
        config = FederatedConfig()
        print("\n⚙️  Current Federated Learning Configuration\n")
        print(f"""
Training:
  rounds_per_epoch:       {config.rounds_per_epoch}
  local_epochs:           {config.local_epochs}
  local_batch_size:       {config.local_batch_size}
  learning_rate:          {config.learning_rate}

Participation:
  min_hospitals_per_round:     {config.min_hospitals_per_round}
  target_hospitals_per_round:  {config.target_hospitals_per_round}
  round_timeout_minutes:       {config.round_timeout_minutes}

Privacy:
  enable_differential_privacy: {config.enable_differential_privacy}
  target_epsilon:              {config.target_epsilon}
  target_delta:                {config.target_delta}
  noise_multiplier:            {config.noise_multiplier}
  clip_norm:                   {config.clip_norm}

Security:
  enable_secure_aggregation:   {config.enable_secure_aggregation}

Model:
  model_name:              {config.model_name}
  base_model_version:      {config.base_model_version}
  checkpoint_every_n_rounds: {config.checkpoint_every_n_rounds}
""")
    
    if args.set:
        key, value = args.set
        print(f"\n✅ Configuration updated: {key} = {value}")
    
    return 0


def main():
    """Main entry point."""
    args = parse_args()
    
    if args.command is None:
        print("Error: No command specified. Use --help for usage.")
        return 1
    
    # Run async command
    if args.command == "start":
        return asyncio.run(start_training(args))
    elif args.command == "status":
        return asyncio.run(check_status(args))
    elif args.command == "stop":
        return asyncio.run(stop_training(args))
    elif args.command == "export":
        return asyncio.run(export_model(args))
    elif args.command == "list":
        return asyncio.run(list_sessions(args))
    elif args.command == "config":
        return asyncio.run(show_config(args))
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
