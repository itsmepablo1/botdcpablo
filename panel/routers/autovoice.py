import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from panel.routers.auth import verify_token
from bot import database as db

router = APIRouter()

@router.get("/{guild_id}")
async def get_autovoice(guild_id: int, payload: dict = Depends(verify_token)):
    cfg = await db.get_guild_config(guild_id)
    return {
        "guild_id":           guild_id,
        "autovoice_channel_id": cfg.get("autovoice_channel_id"),
    }

class AutoVoiceConfig(BaseModel):
    guild_id:   int
    channel_id: Optional[int] = None

@router.post("/update")
async def update_autovoice(data: AutoVoiceConfig, payload: dict = Depends(verify_token)):
    await db.set_guild_config(data.guild_id, autovoice_channel_id=data.channel_id)
    return {"status": "ok"}
