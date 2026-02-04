# ADR-012: Chunked Upload for Mobile Audio

## Status
Accepted

## Date
Day 118 (Phase 3)

## Context

Mobile clients need to upload audio recordings that can be:
1. Large (up to 100MB for long encounters)
2. Recorded in areas with poor connectivity
3. Resumed after network interruptions
4. Processed incrementally for real-time transcription

## Decision

We will implement a chunked upload protocol using the TUS resumable upload standard.

### Protocol Flow

```
┌─────────────┐                              ┌─────────────┐
│   Mobile    │                              │   Server    │
└──────┬──────┘                              └──────┬──────┘
       │                                            │
       │ POST /uploads (create upload)              │
       │ ─────────────────────────────────────────► │
       │                                            │
       │ 201 Created                                │
       │ Location: /uploads/{upload-id}             │
       │ ◄───────────────────────────────────────── │
       │                                            │
       │ PATCH /uploads/{id} (chunk 1)              │
       │ Upload-Offset: 0                           │
       │ Content-Length: 1048576                    │
       │ ─────────────────────────────────────────► │
       │                                            │
       │ 204 No Content                             │
       │ Upload-Offset: 1048576                     │
       │ ◄───────────────────────────────────────── │
       │                                            │
       │ ... (connection lost) ...                  │
       │                                            │
       │ HEAD /uploads/{id} (check progress)        │
       │ ─────────────────────────────────────────► │
       │                                            │
       │ 200 OK                                     │
       │ Upload-Offset: 1048576                     │
       │ ◄───────────────────────────────────────── │
       │                                            │
       │ PATCH /uploads/{id} (chunk 2)              │
       │ Upload-Offset: 1048576                     │
       │ ─────────────────────────────────────────► │
       │                                            │
```

### Implementation

```python
from fastapi import APIRouter, Header, Request, HTTPException
from typing import Optional
import uuid

router = APIRouter()

class ChunkedUpload:
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks
    
    @classmethod
    async def create_upload(
        cls,
        tenant_id: str,
        encounter_id: str,
        upload_length: int,
        content_type: str
    ) -> str:
        upload_id = str(uuid.uuid4())
        await redis.hset(f"upload:{upload_id}", mapping={
            "tenant_id": tenant_id,
            "encounter_id": encounter_id,
            "total_length": upload_length,
            "current_offset": 0,
            "content_type": content_type,
            "created_at": datetime.utcnow().isoformat(),
            "status": "in_progress"
        })
        return upload_id
    
    @classmethod
    async def append_chunk(
        cls,
        upload_id: str,
        offset: int,
        data: bytes
    ) -> int:
        upload = await redis.hgetall(f"upload:{upload_id}")
        current_offset = int(upload["current_offset"])
        
        if offset != current_offset:
            raise HTTPException(409, f"Expected offset {current_offset}")
        
        # Write chunk to temporary storage
        chunk_path = f"/tmp/uploads/{upload_id}/{offset}"
        await write_chunk(chunk_path, data)
        
        # Update offset
        new_offset = offset + len(data)
        await redis.hset(f"upload:{upload_id}", "current_offset", new_offset)
        
        # Trigger incremental processing if streaming transcription
        if int(upload["total_length"]) > new_offset:
            await process_chunk_async(upload_id, offset, data)
        else:
            # Upload complete - finalize
            await cls.finalize_upload(upload_id)
        
        return new_offset
```

## Consequences

### Positive
- Resume uploads after disconnection
- Works on poor mobile networks
- Incremental processing during upload
- Standard protocol (TUS) with client libraries

### Negative
- Server-side chunk management complexity
- Temporary storage requirements
- Cleanup of abandoned uploads needed

## References
- TUS Protocol: https://tus.io/protocols/resumable-upload
- RFC 7233 (Range Requests): https://tools.ietf.org/html/rfc7233
