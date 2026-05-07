import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from panel.routers import auth, dashboard, welcome, roles, autovoice, statuscfg, streaming

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

if __name__ == "__main__":
    import uvicorn
    from bot.config import PANEL_HOST, PANEL_PORT
    uvicorn.run("panel.main:app", host=PANEL_HOST, port=PANEL_PORT, reload=False)
