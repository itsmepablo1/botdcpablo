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
async def get_status(guild_id: int, payload: dict = Depends(verify_token)):
    cfg = await db.get_guild_config(guild_id)
    return {
        "guild_id":                 str(guild_id),
        "status_member_channel_id": _s(cfg.get("status_member_channel_id")),
        "status_online_channel_id": _s(cfg.get("status_online_channel_id")),
        "status_category_id":       _s(cfg.get("status_category_id")),
    }

class StatusConfig(BaseModel):
    guild_id:                 str
    status_member_channel_id: Optional[str] = None
    status_online_channel_id: Optional[str] = None

@router.post("/update")
async def update_status(data: StatusConfig, payload: dict = Depends(verify_token)):
    gid = int(data.guild_id)
    updates = {}
    if data.status_member_channel_id is not None:
        updates["status_member_channel_id"] = _i(data.status_member_channel_id)
    if data.status_online_channel_id is not None:
        updates["status_online_channel_id"] = _i(data.status_online_channel_id)
    if updates:
        await db.set_guild_config(gid, **updates)
    return {"status": "ok", "updated": list(updates.keys())}
