import sys, os, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Depends
from panel.routers.auth import verify_token

router = APIRouter()

WORK_DIR    = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BOT_MODULE  = "bot.main"
LOG_FILE    = os.path.join(WORK_DIR, "bot.log")

# Nama-nama service yang mungkin dipakai (urutan prioritas)
SERVICE_NAMES = [
    "bot-discord",
    "bot-discord.service",
    "discord-bot",
    "discord-bot.service",
    "botdc",
    "botdcpablo",
]

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

def _detect_service_name() -> str | None:
    """Deteksi nama service systemd yang aktif."""
    for name in SERVICE_NAMES:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", name],
                capture_output=True, text=True, timeout=5
            )
            # active / activating / failed = service exist
            if result.stdout.strip() in ("active", "activating", "failed", "inactive"):
                return name
        except Exception:
            continue
    return None

def _try_systemd_restart() -> tuple[bool, str]:
    """Coba restart via systemctl dengan sudo. Return (success, message)."""
    service = _detect_service_name()
    if not service:
        return False, "Tidak ada service systemd yang ditemukan"

    try:
        # Coba dengan sudo
        result = subprocess.run(
            ["sudo", "systemctl", "restart", service],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return True, f"Berhasil restart service: {service}"
        else:
            err = result.stderr.strip() or result.stdout.strip()
            # Coba tanpa sudo (kalau panel jalan sebagai root)
            result2 = subprocess.run(
                ["systemctl", "restart", service],
                capture_output=True, text=True, timeout=15
            )
            if result2.returncode == 0:
                return True, f"Berhasil restart service (tanpa sudo): {service}"
            return False, f"systemctl gagal ({service}): {err}"
    except Exception as e:
        return False, f"Exception saat systemctl: {e}"

def _kill_bot() -> list:
    """Kill semua proses bot (SIGTERM dulu, lalu SIGKILL)."""
    pids = _get_bot_pids()
    for pid in pids:
        try:
            # Kirim SIGTERM dulu
            subprocess.run(["kill", "-15", str(pid)], timeout=3)
        except Exception:
            pass
    if pids:
        time.sleep(3)  # tunggu proses selesai gracefully
    # Paksa kill yang masih hidup
    surviving = _get_bot_pids()
    for pid in surviving:
        try:
            subprocess.run(["kill", "-9", str(pid)], timeout=3)
        except Exception:
            pass
    if surviving:
        time.sleep(1)
    return pids

def _start_bot() -> int | None:
    """Start bot sebagai background process."""
    python = _find_venv_python()
    try:
        with open(LOG_FILE, "a") as log:
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
        print(f"[Panel] Gagal start bot: {e}")
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
async def bot_status(payload: dict = Depends(verify_token)):
    pids    = _get_bot_pids()
    service = _detect_service_name()
    return {
        "running":  len(pids) > 0,
        "pids":     pids,
        "service":  service,
        "work_dir": WORK_DIR,
        "python":   _find_venv_python(),
    }

@router.post("/restart")
async def restart_bot(payload: dict = Depends(verify_token)):
    try:
        # ── Coba systemd (cara terbaik) ──────────────────────────────────────
        ok, msg = _try_systemd_restart()
        if ok:
            return {"status": "ok", "method": "systemd", "message": msg}

        print(f"[Panel] systemd gagal: {msg}, fallback ke kill+start")

        # ── Fallback: kill proses + start ulang ──────────────────────────────
        killed_pids = _kill_bot()
        time.sleep(1)
        new_pid = _start_bot()

        if new_pid:
            return {
                "status":  "ok",
                "method":  "process",
                "message": f"Bot di-restart manual. PID baru: {new_pid}. PID lama: {killed_pids}. (systemd: {msg})",
            }
        else:
            return {
                "status":  "error",
                "message": f"Proses lama ({killed_pids}) di-kill tapi gagal start ulang. systemd error: {msg}. Cek bot.log.",
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/logs")
async def get_logs(lines: int = 100, payload: dict = Depends(verify_token)):
    try:
        # Coba ambil dari journalctl dulu (lebih lengkap)
        service = _detect_service_name()
        if service:
            result = subprocess.run(
                ["journalctl", "-u", service, "-n", str(lines), "--no-pager", "--output=short"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                log_lines = [l.rstrip() for l in result.stdout.splitlines()]
                return {"lines": log_lines, "count": len(log_lines), "source": f"journalctl:{service}"}

        # Fallback: baca bot.log
        if not os.path.exists(LOG_FILE):
            return {"lines": [], "message": f"File log tidak ditemukan: {LOG_FILE}"}
        with open(LOG_FILE, "r", errors="replace") as f:
            all_lines = f.readlines()
        last = [l.rstrip() for l in all_lines[-lines:]]
        return {"lines": last, "count": len(last), "source": LOG_FILE}
    except Exception as e:
        return {"lines": [], "error": str(e)}
