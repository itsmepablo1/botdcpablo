import sys, os, subprocess, signal, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends
from panel.routers.auth import verify_token

router = APIRouter()

BOT_SCRIPT  = "bot.main"
WORK_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # root project
VENV_PYTHON = os.path.join(WORK_DIR, "venv", "bin", "python")
LOG_FILE    = os.path.join(WORK_DIR, "bot.log")

def _is_systemd_available() -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "bot-discord"],
            capture_output=True, text=True, timeout=3
        )
        return result.stdout.strip() in ("active", "inactive", "failed")
    except Exception:
        return False

@router.post("/restart")
async def restart_bot(payload: dict = Depends(verify_token)):
    """Restart bot process — coba systemd dulu, fallback ke pkill+nohup."""
    try:
        if _is_systemd_available():
            result = subprocess.run(
                ["sudo", "systemctl", "restart", "bot-discord"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return {"status": "ok", "method": "systemd", "message": "Bot berhasil di-restart via systemd."}

        # Fallback: pkill lalu nohup
        subprocess.run(["pkill", "-f", BOT_SCRIPT], capture_output=True)
        time.sleep(2)

        python_bin = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
        with open(LOG_FILE, "a") as log:
            subprocess.Popen(
                [python_bin, "-m", BOT_SCRIPT],
                cwd=WORK_DIR,
                stdout=log,
                stderr=log,
                start_new_session=True
            )

        return {"status": "ok", "method": "process", "message": "Bot berhasil di-restart via process."}

    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/status")
async def bot_status(payload: dict = Depends(verify_token)):
    """Cek apakah proses bot sedang berjalan."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", BOT_SCRIPT],
            capture_output=True, text=True
        )
        running = result.returncode == 0
        pids = result.stdout.strip().split("\n") if running else []
        return {"running": running, "pids": [p for p in pids if p]}
    except Exception as e:
        return {"running": False, "error": str(e)}

@router.get("/logs")
async def get_logs(lines: int = 50, payload: dict = Depends(verify_token)):
    """Ambil N baris terakhir dari bot.log."""
    try:
        if not os.path.exists(LOG_FILE):
            return {"lines": [], "message": "File log belum ada."}
        result = subprocess.run(
            ["tail", f"-{lines}", LOG_FILE],
            capture_output=True, text=True, timeout=5
        )
        log_lines = result.stdout.splitlines()
        return {"lines": log_lines, "count": len(log_lines)}
    except Exception as e:
        return {"lines": [], "error": str(e)}
