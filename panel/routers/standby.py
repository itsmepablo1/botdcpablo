"""
panel/routers/standby.py — API untuk Standby Voice Channel
"""
import sys, os
from fastapi import APIRouter, Depends
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from bot import database as db
from panel.routers.auth import verify_token

router = APIRouter()


class StandbyConfig(BaseModel):
    channel_id: int
    enabled: bool = True


@router.get("/{guild_id}")
async def get_standby(guild_id: str, _=Depends(verify_token)):
    cfg = await db.get_standby(int(guild_id))
    return cfg or {"guild_id": int(guild_id), "channel_id": None, "enabled": False}


@router.post("/{guild_id}")
async def set_standby(guild_id: str, data: StandbyConfig, _=Depends(verify_token)):
    await db.set_standby(int(guild_id), data.channel_id, data.enabled)
    return {"ok": True}


@router.delete("/{guild_id}")
async def disable_standby(guild_id: str, _=Depends(verify_token)):
    await db.disable_standby(int(guild_id))
    return {"ok": True}
