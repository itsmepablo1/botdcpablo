import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from panel.routers.auth import verify_token
from bot import database as db

router = APIRouter()

@router.get("/{guild_id}")
async def get_roles(guild_id: int, payload: dict = Depends(verify_token)):
    panels = await db.get_role_panels(guild_id)
    result = []
    for p in panels:
        groups = await db.get_role_groups(p["id"])
        group_data = []
        for g in groups:
            opts = await db.get_role_options(g["id"])
            group_data.append({**g, "options": opts})
        result.append({**p, "groups": group_data})
    return result

class CreatePanelRequest(BaseModel):
    guild_id:    int
    channel_id:  int
    title:       str = "🎭 Pilih Role Kamu"
    description: str = "Pilih satu atau lebih role menggunakan dropdown."

@router.post("/panel/create")
async def create_panel(data: CreatePanelRequest, payload: dict = Depends(verify_token)):
    pid = await db.create_role_panel(data.guild_id, data.channel_id, data.title, data.description)
    return {"status": "ok", "panel_id": pid}

@router.delete("/panel/{panel_id}")
async def delete_panel(panel_id: int, payload: dict = Depends(verify_token)):
    await db.delete_role_panel(panel_id)
    return {"status": "ok"}

class AddGroupRequest(BaseModel):
    panel_id: int
    name:     str

@router.post("/group/add")
async def add_group(data: AddGroupRequest, payload: dict = Depends(verify_token)):
    gid = await db.create_role_group(data.panel_id, data.name)
    return {"status": "ok", "group_id": gid}

class AddRoleRequest(BaseModel):
    group_id:    int
    role_id:     int
    emoji:       Optional[str] = None
    description: Optional[str] = None

@router.post("/role/add")
async def add_role(data: AddRoleRequest, payload: dict = Depends(verify_token)):
    await db.add_role_option(data.group_id, data.role_id, data.emoji, data.description)
    return {"status": "ok"}
