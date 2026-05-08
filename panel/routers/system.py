import sys, os, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends
from panel.routers.auth import verify_token

router = APIRouter()

WORK_DIR    = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BOT_MODULE  = "bot.main"
LOG_FILE    = os.path.join(WORK_DIR, "bot.log")

def _find_venv_python():
    """Cari python di venv, fallback ke sys.executable."""
    candidates = [
        os.path.join(WORK_DIR, "venv", "bin", "python3"),
        os.path.join(WORK_DIR, "venv", "bin", "python"),
        os.path.join(WORK_DIR, "venv", "Scripts", "python.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return sys.executable

def _get_bot_pids() -> list:
    """Dapatkan PID proses bot yang sedang jalan."""
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True, text=True, timeout=5
        )
        pids = []
        for line in result.stdout.splitlines():
            if BOT_MODULE in line and "grep" not in line:
                parts = line.split()
                if len(parts) > 1:
                    try:
                        pids.append(int(parts[1]))
                    except ValueError:
                        pass
        return pids
    except Exception:
        return []

def _try_systemd_restart() -> bool:
    """Coba restart via systemctl, return True jika berhasil."""
    try:
        result = subprocess.run(
            ["systemctl", "restart", "bot-discord"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False

def _kill_bot():
    """Kill semua proses bot yang sedang jalan."""
    pids = _get_bot_pids()
    for pid in pids:
        try:
            subprocess.run(["kill", str(pid)], timeout=3)
        except Exception:
            pass
    if pids:
        time.sleep(2)
    return pids

def _start_bot():
    """Start bot sebagai background process."""
    python = _find_venv_python()
    log_path = LOG_FILE
    try:
        with open(log_path, "a") as log:
            proc = subprocess.Popen(
                [python, "-m", BOT_MODULE],
                cwd=WORK_DIR,
                stdout=log,
                stderr=log,
                start_new_session=True,
                close_fds=True
            )
        return proc.pid
    except Exception as e:
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
async def bot_status(payload: dict = Depends(verify_token)):
    pids = _get_bot_pids()
    return {
        "running": len(pids) > 0,
        "pids":    pids,
        "work_dir": WORK_DIR,
        "python":   _find_venv_python(),
    }

@router.post("/restart")
async def restart_bot(payload: dict = Depends(verify_token)):
    try:
        # Coba systemd dulu
        if _try_systemd_restart():
            return {"status": "ok", "method": "systemd", "message": "Bot berhasil di-restart via systemd."}

        # Fallback: kill + start manual
        killed_pids = _kill_bot()
        new_pid = _start_bot()

        if new_pid:
            return {
                "status":  "ok",
                "method":  "process",
                "message": f"Bot di-restart. PID baru: {new_pid}. PID lama: {killed_pids}",
            }
        else:
            return {
                "status":  "error",
                "message": f"Proses lama ({killed_pids}) sudah di-kill tapi gagal start ulang. Cek bot.log untuk detail.",
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/logs")
async def get_logs(lines: int = 80, payload: dict = Depends(verify_token)):
    try:
        if not os.path.exists(LOG_FILE):
            return {"lines": [], "message": f"File log tidak ditemukan: {LOG_FILE}"}
        with open(LOG_FILE, "r", errors="replace") as f:
            all_lines = f.readlines()
        last = [l.rstrip() for l in all_lines[-lines:]]
        return {"lines": last, "count": len(last), "log_path": LOG_FILE}
    except Exception as e:
        return {"lines": [], "error": str(e)}
