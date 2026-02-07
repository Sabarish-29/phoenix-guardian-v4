"""
Temporal Worker: Phoenix Guardian encounter processing worker.

Starts a Temporal worker process that listens for workflow and activity tasks
on the 'phoenix-guardian-queue' task queue.

Usage:
    python -m phoenix_guardian.workflows.worker

    # Or via CLI:
    temporal server start-dev  # must be running first
    python phoenix_guardian/workflows/worker.py

Environment Variables:
    TEMPORAL_HOST:   Temporal server address (default: localhost:7233)
    TEMPORAL_NS:     Temporal namespace (default: default)
    TASK_QUEUE:      Task queue name (default: phoenix-guardian-queue)
"""

import asyncio
import logging
import os
import signal
import sys

from temporalio.client import Client
from temporalio.worker import Worker

from phoenix_guardian.workflows.encounter_workflow import EncounterProcessingWorkflow
from phoenix_guardian.workflows.activities import (
    validate_encounter,
    generate_soap_activity,
    check_drug_interactions,
    suggest_codes_activity,
    predict_readmission,
    check_security_threats,
    detect_fraud_activity,
    flag_for_review,
    store_encounter,
    delete_soap_draft,
    remove_safety_flags,
    remove_code_suggestions,
)

logger = logging.getLogger("phoenix_guardian.worker")

# Configuration
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NS", "default")
TASK_QUEUE = os.getenv("TASK_QUEUE", "phoenix-guardian-queue")


# All activities the worker should register
ACTIVITIES = [
    validate_encounter,
    generate_soap_activity,
    check_drug_interactions,
    suggest_codes_activity,
    predict_readmission,
    check_security_threats,
    detect_fraud_activity,
    flag_for_review,
    store_encounter,
    # Compensation activities
    delete_soap_draft,
    remove_safety_flags,
    remove_code_suggestions,
]


async def create_worker() -> Worker:
    """Create and configure the Temporal worker.

    Returns:
        Configured Worker instance connected to the Temporal server.
    """
    logger.info(f"Connecting to Temporal at {TEMPORAL_HOST} namespace={TEMPORAL_NAMESPACE}")
    client = await Client.connect(
        TEMPORAL_HOST,
        namespace=TEMPORAL_NAMESPACE,
    )

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[EncounterProcessingWorkflow],
        activities=ACTIVITIES,
    )

    logger.info(
        f"Worker configured — queue={TASK_QUEUE}, "
        f"workflows=1, activities={len(ACTIVITIES)}"
    )
    return worker


async def run_worker() -> None:
    """Start the Temporal worker and run until interrupted."""
    worker = await create_worker()

    # Graceful shutdown on SIGINT/SIGTERM
    shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received — draining worker...")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    logger.info("Phoenix Guardian worker starting...")

    async with worker:
        logger.info(
            f"Worker running — listening on '{TASK_QUEUE}' task queue. "
            f"Press Ctrl+C to stop."
        )
        await shutdown_event.wait()

    logger.info("Worker stopped cleanly.")


def main() -> None:
    """Entry point for the worker process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user.")
    except Exception as e:
        logger.error(f"Worker failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
