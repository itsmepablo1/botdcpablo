"""
panel/routers/schedule.py — API untuk Daily Restart bot
"""
import subprocess
import sys, os
from fastapi import APIRouter, Depends
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from bot import database as db
from panel.routers.auth import verify_token

router = APIRouter()


class ScheduleConfig(BaseModel):
    daily_restart_enabled: bool
    daily_restart_time: str  # format "HH:MM"


@router.get("")
async def get_schedule(_=Depends(verify_token)):
    config = await db.get_schedule_config()
    return config


@router.post("")
async def set_schedule(data: ScheduleConfig, _=Depends(verify_token)):
    # Validasi format waktu HH:MM
    parts = data.daily_restart_time.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return {"ok": False, "error": "Format waktu harus HH:MM"}
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return {"ok": False, "error": "Jam 0-23, menit 0-59"}

    await db.set_schedule_config(data.daily_restart_enabled, data.daily_restart_time)
    return {"ok": True}


@router.post("/restart-now")
async def restart_now(_=Depends(verify_token)):
    """Manual restart bot sekarang."""
    try:
        subprocess.Popen(["systemctl", "restart", "bot-discord.service"])
        return {"ok": True, "message": "Restart bot dikirim"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
