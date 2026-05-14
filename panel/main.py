import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import asyncio
import subprocess
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from panel.routers import auth, dashboard, welcome, roles, autovoice, statuscfg, streaming, system, streamers, schedule, standby

WIB = timezone(timedelta(hours=7))

app = FastAPI(title="Discord Bot Panel", version="1.0.0", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router,       prefix="/api/auth",      tags=["auth"])
app.include_router(dashboard.router,  prefix="/api/dashboard", tags=["dashboard"])
app.include_router(welcome.router,    prefix="/api/welcome",   tags=["welcome"])
app.include_router(roles.router,      prefix="/api/roles",     tags=["roles"])
app.include_router(autovoice.router,  prefix="/api/autovoice", tags=["autovoice"])
app.include_router(statuscfg.router,  prefix="/api/status",    tags=["status"])
app.include_router(streaming.router,  prefix="/api/streaming", tags=["streaming"])
app.include_router(streamers.router,  prefix="/api/streamers", tags=["streamers"])
app.include_router(schedule.router,   prefix="/api/schedule",  tags=["schedule"])
app.include_router(standby.router,    prefix="/api/standby",   tags=["standby"])
app.include_router(system.router,     prefix="/api/system",    tags=["system"])

# ── Static Files ──────────────────────────────────────────────────────────────
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/login")
async def login_page():
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))

@app.get("/")
async def index_page():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# ── Daily Restart Scheduler ───────────────────────────────────────────────────

async def _daily_restart_loop():
    """Loop setiap menit, cek apakah saatnya restart bot."""
    from bot import database as db
    last_triggered = None  # Simpan menit terakhir trigger agar tidak dobel

    print("[Schedule] Daily restart scheduler started", flush=True)
    while True:
        try:
            await asyncio.sleep(60)
            config = await db.get_schedule_config()
            if not config.get("daily_restart_enabled"):
                continue

            restart_time = config.get("daily_restart_time", "04:00")
            now_wib = datetime.now(WIB)
            now_hhmm = now_wib.strftime("%H:%M")

            if now_hhmm == restart_time and last_triggered != now_wib.date():
                last_triggered = now_wib.date()
                print(f"[Schedule] Daily restart dipicu pukul {now_hhmm} WIB", flush=True)
                subprocess.Popen(["systemctl", "restart", "bot-discord.service"])

        except Exception as e:
            print(f"[Schedule] Error: {e}", flush=True)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(_daily_restart_loop())


if __name__ == "__main__":
    import uvicorn
    from bot.config import PANEL_HOST, PANEL_PORT
    uvicorn.run("panel.main:app", host=PANEL_HOST, port=PANEL_PORT, reload=False)
