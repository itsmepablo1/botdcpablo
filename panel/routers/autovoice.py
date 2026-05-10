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
async def get_autovoice(guild_id: int, payload: dict = Depends(verify_token)):
    cfg = await db.get_guild_config(guild_id)
    return {
        "guild_id":             str(guild_id),
        "autovoice_channel_id": _s(cfg.get("autovoice_channel_id")),
    }

@router.get("/{guild_id}/active-vcs")
async def get_active_vcs(guild_id: int, payload: dict = Depends(verify_token)):
    vcs = await db.get_all_auto_voice_details(guild_id)
    return [{**v,
             "channel_id": str(v["channel_id"]),
             "guild_id":   str(v["guild_id"]),
             "owner_id":   str(v["owner_id"])} for v in vcs]

class AutoVoiceConfig(BaseModel):
    guild_id:   str
    channel_id: Optional[str] = None

@router.post("/update")
async def update_autovoice(data: AutoVoiceConfig, payload: dict = Depends(verify_token)):
    gid = int(data.guild_id)
    await db.set_guild_config(gid, autovoice_channel_id=_i(data.channel_id))
    return {"status": "ok"}
