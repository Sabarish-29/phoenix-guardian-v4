"""
Phoenix Guardian - WebSocket Load Test
Week 35: Integration Testing + Polish (Days 171-175)

Performance testing for WebSocket connections.
Tests 10,000 concurrent WebSocket connections for real-time features.

Test Scenarios:
- Concurrent WebSocket connections
- Real-time threat notifications
- Live encounter updates
- Dashboard metrics streaming
- Connection stability under load
- Reconnection handling

Run: python load_test_websocket.py --host=wss://api.phoenix-guardian.health --connections=10000
"""

import asyncio
import websockets
import json
import time
import random
import uuid
import argparse
import statistics
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class TestConfig:
    """WebSocket load test configuration."""
    host: str = "wss://api.phoenix-guardian.health"
    path: str = "/ws/v1"
    num_connections: int = 10000
    ramp_up_seconds: int = 60
    test_duration_seconds: int = 300
    messages_per_connection: int = 10
    reconnect_on_failure: bool = True
    max_reconnect_attempts: int = 3
    
    # SLAs
    max_connection_time_ms: float = 1000
    max_message_latency_ms: float = 100
    min_success_rate: float = 0.99


class MessageType(Enum):
    """WebSocket message types."""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PING = "ping"
    PONG = "pong"
    THREAT_ALERT = "threat_alert"
    ENCOUNTER_UPDATE = "encounter_update"
    METRICS_UPDATE = "metrics_update"


# ============================================================================
# Metrics Collection
# ============================================================================

@dataclass
class ConnectionMetrics:
    """Metrics for a single WebSocket connection."""
    connection_id: str
    tenant_id: str
    connected_at: Optional[datetime] = None
    disconnected_at: Optional[datetime] = None
    connection_time_ms: float = 0
    messages_sent: int = 0
    messages_received: int = 0
    errors: int = 0
    reconnects: int = 0
    message_latencies: List[float] = field(default_factory=list)


@dataclass
class AggregateMetrics:
    """Aggregate metrics across all connections."""
    total_connections: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    total_messages_sent: int = 0
    total_messages_received: int = 0
    total_errors: int = 0
    total_reconnects: int = 0
    connection_times: List[float] = field(default_factory=list)
    message_latencies: List[float] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def add_connection_metrics(self, metrics: ConnectionMetrics):
        """Add metrics from a connection."""
        self.total_connections += 1
        if metrics.connected_at:
            self.successful_connections += 1
            self.connection_times.append(metrics.connection_time_ms)
        else:
            self.failed_connections += 1
        
        self.total_messages_sent += metrics.messages_sent
        self.total_messages_received += metrics.messages_received
        self.total_errors += metrics.errors
        self.total_reconnects += metrics.reconnects
        self.message_latencies.extend(metrics.message_latencies)
    
    def get_p50_connection_time(self) -> float:
        """Get P50 connection time."""
        if not self.connection_times:
            return 0
        return statistics.median(self.connection_times)
    
    def get_p95_connection_time(self) -> float:
        """Get P95 connection time."""
        if not self.connection_times:
            return 0
        sorted_times = sorted(self.connection_times)
        index = int(len(sorted_times) * 0.95)
        return sorted_times[min(index, len(sorted_times) - 1)]
    
    def get_p99_connection_time(self) -> float:
        """Get P99 connection time."""
        if not self.connection_times:
            return 0
        sorted_times = sorted(self.connection_times)
        index = int(len(sorted_times) * 0.99)
        return sorted_times[min(index, len(sorted_times) - 1)]
    
    def get_p50_message_latency(self) -> float:
        """Get P50 message latency."""
        if not self.message_latencies:
            return 0
        return statistics.median(self.message_latencies)
    
    def get_p95_message_latency(self) -> float:
        """Get P95 message latency."""
        if not self.message_latencies:
            return 0
        sorted_times = sorted(self.message_latencies)
        index = int(len(sorted_times) * 0.95)
        return sorted_times[min(index, len(sorted_times) - 1)]
    
    def get_p99_message_latency(self) -> float:
        """Get P99 message latency."""
        if not self.message_latencies:
            return 0
        sorted_times = sorted(self.message_latencies)
        index = int(len(sorted_times) * 0.99)
        return sorted_times[min(index, len(sorted_times) - 1)]
    
    def get_success_rate(self) -> float:
        """Get connection success rate."""
        if self.total_connections == 0:
            return 0
        return self.successful_connections / self.total_connections
    
    def get_throughput(self) -> float:
        """Get messages per second."""
        if not self.start_time or not self.end_time:
            return 0
        duration = (self.end_time - self.start_time).total_seconds()
        if duration == 0:
            return 0
        return self.total_messages_received / duration


# ============================================================================
# WebSocket Client Simulator
# ============================================================================

class WebSocketClient:
    """Simulates a single WebSocket client."""
    
    def __init__(
        self,
        config: TestConfig,
        connection_id: str,
        tenant_id: str
    ):
        self.config = config
        self.connection_id = connection_id
        self.tenant_id = tenant_id
        self.user_id = f"user-{uuid.uuid4().hex[:8]}"
        
        self.metrics = ConnectionMetrics(
            connection_id=connection_id,
            tenant_id=tenant_id
        )
        
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.subscriptions: List[str] = []
    
    async def connect(self) -> bool:
        """Establish WebSocket connection."""
        start_time = time.time()
        
        try:
            uri = f"{self.config.host}{self.config.path}"
            
            # Add query parameters for auth simulation
            params = f"?tenant_id={self.tenant_id}&user_id={self.user_id}"
            
            self.ws = await asyncio.wait_for(
                websockets.connect(
                    uri + params,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5
                ),
                timeout=10
            )
            
            self.metrics.connected_at = datetime.utcnow()
            self.metrics.connection_time_ms = (time.time() - start_time) * 1000
            self.running = True
            
            # Send initial subscription
            await self._subscribe([
                "threats",
                "encounters",
                "metrics"
            ])
            
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"Connection timeout: {self.connection_id}")
            self.metrics.errors += 1
            return False
            
        except Exception as e:
            logger.warning(f"Connection failed {self.connection_id}: {e}")
            self.metrics.errors += 1
            return False
    
    async def disconnect(self):
        """Close WebSocket connection."""
        self.running = False
        self.metrics.disconnected_at = datetime.utcnow()
        
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
    
    async def _subscribe(self, channels: List[str]):
        """Subscribe to channels."""
        message = {
            "type": MessageType.SUBSCRIBE.value,
            "channels": channels,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self._send_message(message)
        self.subscriptions.extend(channels)
    
    async def _send_message(self, message: Dict[str, Any]):
        """Send a message."""
        if not self.ws:
            return
        
        try:
            message["client_id"] = self.connection_id
            message["sent_at"] = time.time()
            
            await self.ws.send(json.dumps(message))
            self.metrics.messages_sent += 1
            
        except Exception as e:
            logger.warning(f"Send failed {self.connection_id}: {e}")
            self.metrics.errors += 1
    
    async def _receive_message(self) -> Optional[Dict[str, Any]]:
        """Receive a message."""
        if not self.ws:
            return None
        
        try:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=5)
            message = json.loads(raw)
            self.metrics.messages_received += 1
            
            # Calculate latency if sent_at is present
            if "sent_at" in message:
                latency = (time.time() - message["sent_at"]) * 1000
                self.metrics.message_latencies.append(latency)
            
            return message
            
        except asyncio.TimeoutError:
            return None
            
        except Exception as e:
            logger.warning(f"Receive failed {self.connection_id}: {e}")
            self.metrics.errors += 1
            return None
    
    async def run_session(self, duration_seconds: int):
        """Run a complete WebSocket session."""
        if not await self.connect():
            return
        
        end_time = time.time() + duration_seconds
        
        try:
            while self.running and time.time() < end_time:
                # Send ping periodically
                if random.random() < 0.1:  # 10% chance each iteration
                    await self._send_ping()
                
                # Receive messages
                message = await self._receive_message()
                
                if message:
                    await self._handle_message(message)
                
                # Small delay to prevent tight loop
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.warning(f"Session error {self.connection_id}: {e}")
            self.metrics.errors += 1
            
        finally:
            await self.disconnect()
    
    async def _send_ping(self):
        """Send a ping message."""
        message = {
            "type": MessageType.PING.value,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self._send_message(message)
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle received message."""
        msg_type = message.get("type")
        
        if msg_type == MessageType.PONG.value:
            # Ping/pong response
            pass
        
        elif msg_type == MessageType.THREAT_ALERT.value:
            # Handle threat alert
            logger.debug(f"Threat alert received: {self.connection_id}")
        
        elif msg_type == MessageType.ENCOUNTER_UPDATE.value:
            # Handle encounter update
            logger.debug(f"Encounter update received: {self.connection_id}")
        
        elif msg_type == MessageType.METRICS_UPDATE.value:
            # Handle metrics update
            logger.debug(f"Metrics update received: {self.connection_id}")


# ============================================================================
# Load Test Orchestrator
# ============================================================================

class WebSocketLoadTest:
    """Orchestrates WebSocket load testing."""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.clients: List[WebSocketClient] = []
        self.aggregate_metrics = AggregateMetrics()
        self.running = False
    
    async def run(self):
        """Run the load test."""
        logger.info("=" * 60)
        logger.info("Phoenix Guardian WebSocket Load Test")
        logger.info("=" * 60)
        logger.info(f"Target Host: {self.config.host}")
        logger.info(f"Connections: {self.config.num_connections}")
        logger.info(f"Ramp-up: {self.config.ramp_up_seconds}s")
        logger.info(f"Duration: {self.config.test_duration_seconds}s")
        logger.info("=" * 60)
        
        self.running = True
        self.aggregate_metrics.start_time = datetime.utcnow()
        
        # Create clients
        for i in range(self.config.num_connections):
            tenant_id = f"hospital-{(i % 10) + 1:03d}"
            client = WebSocketClient(
                self.config,
                f"client-{i:05d}",
                tenant_id
            )
            self.clients.append(client)
        
        # Ramp up connections
        batch_size = max(1, self.config.num_connections // self.config.ramp_up_seconds)
        
        logger.info(f"Starting ramp-up: {batch_size} connections/second")
        
        tasks = []
        for i, client in enumerate(self.clients):
            # Create session task
            task = asyncio.create_task(
                client.run_session(self.config.test_duration_seconds)
            )
            tasks.append(task)
            
            # Rate limit connection attempts
            if (i + 1) % batch_size == 0:
                await asyncio.sleep(1)
                connected = sum(1 for c in self.clients[:i+1] if c.metrics.connected_at)
                logger.info(f"Connections: {connected}/{i+1}")
        
        logger.info("Ramp-up complete, running test...")
        
        # Wait for all sessions to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        self.aggregate_metrics.end_time = datetime.utcnow()
        
        # Collect metrics
        for client in self.clients:
            self.aggregate_metrics.add_connection_metrics(client.metrics)
        
        self._print_results()
    
    def _print_results(self):
        """Print test results."""
        logger.info("")
        logger.info("=" * 60)
        logger.info("WebSocket Load Test Results")
        logger.info("=" * 60)
        
        m = self.aggregate_metrics
        
        logger.info(f"Total Connections Attempted: {m.total_connections}")
        logger.info(f"Successful Connections: {m.successful_connections}")
        logger.info(f"Failed Connections: {m.failed_connections}")
        logger.info(f"Success Rate: {m.get_success_rate() * 100:.2f}%")
        logger.info("")
        
        logger.info(f"Messages Sent: {m.total_messages_sent}")
        logger.info(f"Messages Received: {m.total_messages_received}")
        logger.info(f"Throughput: {m.get_throughput():.2f} msg/s")
        logger.info("")
        
        logger.info("Connection Time (ms):")
        logger.info(f"  P50: {m.get_p50_connection_time():.2f}")
        logger.info(f"  P95: {m.get_p95_connection_time():.2f}")
        logger.info(f"  P99: {m.get_p99_connection_time():.2f}")
        logger.info("")
        
        logger.info("Message Latency (ms):")
        logger.info(f"  P50: {m.get_p50_message_latency():.2f}")
        logger.info(f"  P95: {m.get_p95_message_latency():.2f}")
        logger.info(f"  P99: {m.get_p99_message_latency():.2f}")
        logger.info("")
        
        # Check SLAs
        logger.info("SLA Verification:")
        
        sla_passed = True
        
        p99_conn = m.get_p99_connection_time()
        if p99_conn > self.config.max_connection_time_ms:
            logger.info(f"  ❌ Connection Time P99: {p99_conn:.2f}ms > {self.config.max_connection_time_ms}ms")
            sla_passed = False
        else:
            logger.info(f"  ✅ Connection Time P99: {p99_conn:.2f}ms <= {self.config.max_connection_time_ms}ms")
        
        p99_latency = m.get_p99_message_latency()
        if p99_latency > self.config.max_message_latency_ms:
            logger.info(f"  ❌ Message Latency P99: {p99_latency:.2f}ms > {self.config.max_message_latency_ms}ms")
            sla_passed = False
        else:
            logger.info(f"  ✅ Message Latency P99: {p99_latency:.2f}ms <= {self.config.max_message_latency_ms}ms")
        
        success_rate = m.get_success_rate()
        if success_rate < self.config.min_success_rate:
            logger.info(f"  ❌ Success Rate: {success_rate * 100:.2f}% < {self.config.min_success_rate * 100}%")
            sla_passed = False
        else:
            logger.info(f"  ✅ Success Rate: {success_rate * 100:.2f}% >= {self.config.min_success_rate * 100}%")
        
        logger.info("")
        if sla_passed:
            logger.info("🎉 ALL SLAs PASSED")
        else:
            logger.info("⚠️  SOME SLAs FAILED")
        
        logger.info("=" * 60)


# ============================================================================
# Simulated Server for Testing
# ============================================================================

class SimulatedWebSocketServer:
    """Simulated WebSocket server for local testing."""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: set = set()
        self.running = False
    
    async def handler(self, websocket, path):
        """Handle WebSocket connection."""
        self.clients.add(websocket)
        
        try:
            async for message in websocket:
                data = json.loads(message)
                
                # Echo back with timestamp
                response = {
                    "type": "pong" if data.get("type") == "ping" else "ack",
                    "original_type": data.get("type"),
                    "sent_at": data.get("sent_at"),
                    "server_time": time.time()
                }
                
                await websocket.send(json.dumps(response))
                
                # Simulate occasional broadcast
                if random.random() < 0.01:
                    await self._broadcast_threat()
                    
        except websockets.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
    
    async def _broadcast_threat(self):
        """Broadcast a threat alert to all clients."""
        message = {
            "type": "threat_alert",
            "threat_id": str(uuid.uuid4()),
            "severity": random.choice(["low", "medium", "high", "critical"]),
            "sent_at": time.time()
        }
        
        for client in self.clients.copy():
            try:
                await client.send(json.dumps(message))
            except Exception:
                self.clients.discard(client)
    
    async def start(self):
        """Start the server."""
        self.running = True
        async with websockets.serve(self.handler, self.host, self.port):
            logger.info(f"Simulated server running on ws://{self.host}:{self.port}")
            while self.running:
                await asyncio.sleep(1)
    
    def stop(self):
        """Stop the server."""
        self.running = False


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Phoenix Guardian WebSocket Load Test"
    )
    parser.add_argument(
        "--host",
        default="ws://localhost:8765",
        help="WebSocket server URL"
    )
    parser.add_argument(
        "--connections",
        type=int,
        default=100,
        help="Number of concurrent connections"
    )
    parser.add_argument(
        "--ramp-up",
        type=int,
        default=10,
        help="Ramp-up time in seconds"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Test duration in seconds"
    )
    parser.add_argument(
        "--simulate-server",
        action="store_true",
        help="Start a simulated WebSocket server for testing"
    )
    
    args = parser.parse_args()
    
    if args.simulate_server:
        # Start simulated server and client test
        server = SimulatedWebSocketServer()
        server_task = asyncio.create_task(server.start())
        
        await asyncio.sleep(1)  # Let server start
        
        config = TestConfig(
            host="ws://localhost:8765",
            path="",
            num_connections=args.connections,
            ramp_up_seconds=args.ramp_up,
            test_duration_seconds=args.duration
        )
        
        test = WebSocketLoadTest(config)
        await test.run()
        
        server.stop()
        await server_task
        
    else:
        # Run against specified host
        config = TestConfig(
            host=args.host,
            num_connections=args.connections,
            ramp_up_seconds=args.ramp_up,
            test_duration_seconds=args.duration
        )
        
        test = WebSocketLoadTest(config)
        await test.run()


if __name__ == "__main__":
    asyncio.run(main())
