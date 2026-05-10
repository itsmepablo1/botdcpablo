import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from typing import Optional, Any
from panel.routers.auth import verify_token
from bot import database as db

router = APIRouter()
def _s(v): return str(v) if v is not None else None

class StreamingConfig(BaseModel):
    guild_id:          Any
    channel_id:        Any = None
    role_id:           Any = None
    on_stream_role_id: Any = None

@router.get("/{guild_id}")
async def get_streaming(guild_id: int, payload: dict = Depends(verify_token)):
    cfg = await db.get_guild_config(guild_id)
    return {
        "guild_id":                    str(guild_id),
        "streaming_channel_id":        _s(cfg.get("streaming_channel_id")),
        "streaming_role_id":           _s(cfg.get("streaming_role_id")),
        "streaming_on_stream_role_id": _s(cfg.get("streaming_on_stream_role_id")),
    }

@router.post("/update")
async def update_streaming(data: StreamingConfig, payload: dict = Depends(verify_token)):
    gid = int(str(data.guild_id)) if data.guild_id else None
    if not gid:
        return {"status": "error", "message": "guild_id required"}
    updates = {}
    if data.channel_id is not None:
        updates["streaming_channel_id"] = int(str(data.channel_id)) if data.channel_id else None
    if data.role_id is not None:
        updates["streaming_role_id"] = int(str(data.role_id)) if data.role_id else None
    if data.on_stream_role_id is not None:
        updates["streaming_on_stream_role_id"] = int(str(data.on_stream_role_id)) if data.on_stream_role_id else None
    if updates:
        await db.set_guild_config(gid, **updates)
    return {"status": "ok", "updated": list(updates.keys())}
