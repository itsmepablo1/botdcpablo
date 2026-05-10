import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from panel.routers.auth import verify_token
from bot import database as db

router = APIRouter()
def _s(v): return str(v) if v is not None else None
def _i(v): return int(v) if v else None

@router.get("/{guild_id}")
async def get_streaming(guild_id: int, payload: dict = Depends(verify_token)):
    cfg = await db.get_guild_config(guild_id)
    return {
        "guild_id":                    str(guild_id),
        "streaming_channel_id":        _s(cfg.get("streaming_channel_id")),
        "streaming_role_id":           _s(cfg.get("streaming_role_id")),
        "streaming_on_stream_role_id": _s(cfg.get("streaming_on_stream_role_id")),
    }

class StreamingConfig(BaseModel):
    guild_id:          str
    channel_id:        Optional[str] = None
    role_id:           Optional[str] = None
    on_stream_role_id: Optional[str] = None

@router.post("/update")
async def update_streaming(data: StreamingConfig, payload: dict = Depends(verify_token)):
    gid = int(data.guild_id)
    updates = {}
    if data.channel_id is not None:
        updates["streaming_channel_id"] = _i(data.channel_id)
    if data.role_id is not None:
        updates["streaming_role_id"] = _i(data.role_id)
    if data.on_stream_role_id is not None:
        updates["streaming_on_stream_role_id"] = _i(data.on_stream_role_id)
    if updates:
        await db.set_guild_config(gid, **updates)
    return {"status": "ok", "updated": list(updates.keys())}
