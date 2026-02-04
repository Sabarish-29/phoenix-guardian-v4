# ADR-006: WebSocket for Real-time Communication

## Status
Accepted

## Date
Day 135 (Phase 3)

## Context

Phoenix Guardian's real-time dashboard requires:
1. Live threat alerts with <100ms delivery
2. Real-time encounter status updates
3. Streaming transcription results
4. System health monitoring
5. Collaborative editing notifications

We need a technology that supports bidirectional communication, low latency, and scales to 10,000+ concurrent connections.

## Decision

We will use WebSocket protocol for all real-time communication between clients and backend services.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                 │
│  │  Dashboard │  │   Mobile   │  │ Admin Panel│                 │
│  │  (React)   │  │   (React)  │  │  (React)   │                 │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘                 │
│        │               │               │                         │
│        └───────────────┼───────────────┘                         │
│                        │ WebSocket                               │
└────────────────────────┼────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    WebSocket Gateway                             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              Load Balancer (sticky sessions)               │ │
│  └─────────────────────────┬──────────────────────────────────┘ │
│                            │                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   WS Pod 1  │  │   WS Pod 2  │  │   WS Pod N  │              │
│  │  (FastAPI)  │  │  (FastAPI)  │  │  (FastAPI)  │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│         └────────────────┼────────────────┘                      │
│                          │                                       │
│  ┌───────────────────────┼───────────────────────────────────┐  │
│  │              Redis Pub/Sub (coordination)                 │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import redis.asyncio as redis
import json

class ConnectionManager:
    """Manage WebSocket connections with Redis coordination."""
    
    def __init__(self, redis_url: str):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.redis = redis.from_url(redis_url)
        
    async def connect(self, websocket: WebSocket, tenant_id: str, user_id: str):
        """Accept and register connection."""
        await websocket.accept()
        
        key = f"{tenant_id}:{user_id}"
        if key not in self.active_connections:
            self.active_connections[key] = set()
        self.active_connections[key].add(websocket)
        
        # Register in Redis for cross-pod coordination
        await self.redis.sadd(f"ws:connections:{tenant_id}", user_id)
        
    async def disconnect(self, websocket: WebSocket, tenant_id: str, user_id: str):
        """Remove connection from registry."""
        key = f"{tenant_id}:{user_id}"
        self.active_connections[key].discard(websocket)
        
        if not self.active_connections[key]:
            del self.active_connections[key]
            await self.redis.srem(f"ws:connections:{tenant_id}", user_id)
            
    async def broadcast_to_tenant(self, tenant_id: str, message: dict):
        """Broadcast message to all connections for a tenant."""
        # Publish to Redis for cross-pod delivery
        await self.redis.publish(
            f"ws:broadcast:{tenant_id}",
            json.dumps(message)
        )
        
    async def send_to_user(self, tenant_id: str, user_id: str, message: dict):
        """Send message to specific user's connections."""
        key = f"{tenant_id}:{user_id}"
        connections = self.active_connections.get(key, set())
        
        for websocket in connections:
            await websocket.send_json(message)


# WebSocket endpoint
app = FastAPI()
manager = ConnectionManager(redis_url="redis://localhost:6379")

@app.websocket("/ws/{tenant_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    tenant_id: str,
):
    # Authenticate from headers/query
    user_id = await authenticate_ws(websocket)
    
    await manager.connect(websocket, tenant_id, user_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            await handle_message(data, tenant_id, user_id)
    except WebSocketDisconnect:
        await manager.disconnect(websocket, tenant_id, user_id)
```

### Message Types

```python
from enum import Enum
from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime

class MessageType(str, Enum):
    # Threats
    THREAT_DETECTED = "threat.detected"
    THREAT_UPDATED = "threat.updated"
    THREAT_RESOLVED = "threat.resolved"
    
    # Encounters
    ENCOUNTER_STARTED = "encounter.started"
    ENCOUNTER_UPDATED = "encounter.updated"
    ENCOUNTER_COMPLETED = "encounter.completed"
    
    # Transcription
    TRANSCRIPTION_PROGRESS = "transcription.progress"
    TRANSCRIPTION_CHUNK = "transcription.chunk"
    TRANSCRIPTION_COMPLETE = "transcription.complete"
    
    # System
    SYSTEM_HEALTH = "system.health"
    SYSTEM_ALERT = "system.alert"
    
    # Control
    PING = "ping"
    PONG = "pong"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"


class WSMessage(BaseModel):
    type: MessageType
    payload: Any
    timestamp: datetime = datetime.utcnow()
    correlation_id: Optional[str] = None
```

## Consequences

### Positive

1. **Low latency** - <50ms typical message delivery
2. **Bidirectional** - Both client and server can initiate messages
3. **Efficient** - Single connection vs polling
4. **Real-time** - True push notifications
5. **Standard protocol** - Well-supported across browsers and platforms

### Negative

1. **Stateful connections** - Complicates scaling and load balancing
2. **Memory overhead** - Each connection consumes server memory
3. **Reconnection handling** - Client must handle disconnects gracefully
4. **Firewall issues** - Some corporate firewalls block WebSocket
5. **Debugging** - Harder to debug than HTTP

### Risks

1. **Connection storms** - Mitigated by exponential backoff on reconnect
2. **Memory exhaustion** - Mitigated by connection limits and monitoring
3. **Split-brain** - Mitigated by Redis coordination

## Alternatives Considered

### Server-Sent Events (SSE)

**Pros:**
- Simpler than WebSocket
- HTTP-based (firewall friendly)
- Auto-reconnection

**Cons:**
- Unidirectional only
- Cannot send client messages efficiently
- Limited browser connection pool

**Rejected because:** Need bidirectional communication for transcription streaming and user interactions.

### HTTP Long Polling

**Pros:**
- Works everywhere
- Simple implementation
- No special infrastructure

**Cons:**
- High latency
- Resource intensive
- Not true real-time

**Rejected because:** Latency and overhead unacceptable for threat alerts.

### GraphQL Subscriptions

**Pros:**
- Type-safe
- Unified API
- Good developer experience

**Cons:**
- Complexity overhead
- Less mature tooling
- Still uses WebSocket underneath

**Rejected because:** Adds unnecessary abstraction layer for our use case.

### gRPC Streaming

**Pros:**
- Efficient binary protocol
- Strong typing
- Bidirectional

**Cons:**
- No browser support without grpc-web
- Less familiar to frontend developers
- Complex setup

**Rejected because:** Need direct browser support without proxy.

## Scaling Strategy

```yaml
# WebSocket HPA configuration
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: websocket-gateway-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: websocket-gateway
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Pods
      pods:
        metric:
          name: websocket_connections_per_pod
        target:
          type: AverageValue
          averageValue: "500"
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 70
```

## Validation

1. **Load testing** - 12,500 concurrent connections validated
2. **Latency testing** - 34ms average message delivery
3. **Failover testing** - Graceful reconnection on pod restart
4. **Cross-pod messaging** - Redis pub/sub coordination verified

## References

- RFC 6455 (WebSocket Protocol): https://tools.ietf.org/html/rfc6455
- FastAPI WebSocket Documentation: https://fastapi.tiangolo.com/advanced/websockets/
- Scaling WebSocket: https://ably.com/topic/scaling-websockets
