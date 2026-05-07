import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from panel.routers.auth import verify_token
from bot import database as db

router = APIRouter()

class WelcomeConfig(BaseModel):
    guild_id: int
    welcome_channel_id: Optional[int] = None
    welcome_message: Optional[str] = None
    leave_channel_id: Optional[int] = None
    leave_message: Optional[str] = None

@router.get("/{guild_id}")
async def get_welcome(guild_id: int, payload: dict = Depends(verify_token)):
    cfg = await db.get_guild_config(guild_id)
    return {
        "guild_id":           guild_id,
        "welcome_channel_id": cfg.get("welcome_channel_id"),
        "welcome_message":    cfg.get("welcome_message"),
        "welcome_background": cfg.get("welcome_background"),
        "leave_channel_id":   cfg.get("leave_channel_id"),
        "leave_message":      cfg.get("leave_message"),
        "leave_background":   cfg.get("leave_background"),
    }

@router.post("/update")
async def update_welcome(data: WelcomeConfig, payload: dict = Depends(verify_token)):
    updates = {}
    if data.welcome_channel_id is not None:
        updates["welcome_channel_id"] = data.welcome_channel_id
    if data.welcome_message is not None:
        updates["welcome_message"] = data.welcome_message
    if data.leave_channel_id is not None:
        updates["leave_channel_id"] = data.leave_channel_id
    if data.leave_message is not None:
        updates["leave_message"] = data.leave_message
    if updates:
        await db.set_guild_config(data.guild_id, **updates)
    return {"status": "ok", "updated": list(updates.keys())}
