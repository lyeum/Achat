"""프로젝트 루트 진입점 — QML + PySide6 플로팅 UI 실행."""

from __future__ import annotations

import faulthandler
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

faulthandler.enable()

# Qt 초기화 전 입력기 / 플랫폼 환경변수 설정 (WSL2 한글 입력)
# WAYLAND_DISPLAY가 있으면 Qt ibus 플러그인이 portal 모드를 강제 사용하지만,
if sys.platform != "win32":
    # WSL2 환경에서 org.freedesktop.IBus.Portal은 session bus에 미등록 → input context 생성 실패
    # 주의: libxcb-cursor0 설치 필요 (sudo apt-get install -y libxcb-cursor0)
    os.environ.pop("WAYLAND_DISPLAY", None)
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
    os.environ["QT_IM_MODULE"] = "ibus"
    os.environ["GTK_IM_MODULE"] = "ibus"
    os.environ["XMODIFIERS"] = "@im=ibus"
os.environ["IBUS_USE_PORTAL"] = "0"              # setdefault 대신 강제 오버라이드


def _ensure_dbus_session() -> None:
    """dbus 세션 버스가 없으면 dbus-launch로 기동하고 환경변수를 주입한다.
    WSL2 기본 환경에는 dbus 세션이 없어 ibus가 Qt와 통신 불가.
    """
    if os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return
    try:
        result = subprocess.run(
            ["dbus-launch", "--sh-syntax"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            # 예: DBUS_SESSION_BUS_ADDRESS='unix:path=...'; export DBUS_SESSION_BUS_ADDRESS;
            if "=" in line and not line.startswith("#"):
                key, _, rest = line.partition("=")
                key = key.strip()
                val = rest.split(";")[0].strip().strip("'\"")
                if key in ("DBUS_SESSION_BUS_ADDRESS", "DBUS_SESSION_BUS_PID"):
                    os.environ[key] = val
    except Exception:
        pass


def _ensure_ibus_hangul() -> None:
    """ibus-daemon을 기동하고 hangul 엔진으로 설정한다.
    bus 파일 PID와 실행 중인 daemon PID가 다르면 재시작해 fresh bus 파일을 확보한다.
    ibus 미설치 환경에서는 조용히 무시.
    """
    import time
    try:
        # 1. 실행 중인 ibus-daemon PID 확인
        pgrep = subprocess.run(
            ["pgrep", "-x", "ibus-daemon"],
            capture_output=True, text=True, timeout=2,
        )
        running_pid = int(pgrep.stdout.strip()) if pgrep.returncode == 0 else None

        # 2. bus 파일의 PID 확인
        machine_id = Path("/etc/machine-id").read_text().strip()
        display = os.environ.get("DISPLAY", ":0").lstrip(":").split(".")[0]
        bus_file = Path.home() / f".config/ibus/bus/{machine_id}-unix-{display}"
        if not bus_file.exists():
            wl = "wayland-0"  # WAYLAND_DISPLAY는 이미 언셋됨
            bus_file = Path.home() / f".config/ibus/bus/{machine_id}-unix-{wl}"

        bus_pid = None
        if bus_file.exists():
            for line in bus_file.read_text().splitlines():
                if line.startswith("IBUS_DAEMON_PID="):
                    try:
                        bus_pid = int(line.split("=", 1)[1])
                    except ValueError:
                        pass
                    break

        # 3. 실행 중 daemon이 없거나 bus 파일 PID와 불일치(stale) → 재시작
        need_restart = (running_pid is None) or (bus_pid != running_pid)
        if need_restart:
            if running_pid is not None:
                subprocess.run(["kill", str(running_pid)], capture_output=True, timeout=2)
                time.sleep(0.5)
            subprocess.run(
                ["ibus-daemon", "-d", "--xim"],
                capture_output=True, timeout=5,
            )
            time.sleep(1.5)  # 데몬 초기화 + bus 파일 기록 대기

        # 4. 엔진이 hangul이 아니면 전환
        result = subprocess.run(
            ["ibus", "engine"],
            capture_output=True, text=True, timeout=2,
        )
        if "hangul" not in result.stdout.lower():
            subprocess.run(
                ["ibus", "engine", "hangul"],
                capture_output=True, timeout=2,
            )

        # 5. Ctrl+Space를 한/영 토글 키로 등록 (기본값엔 없음 — 환경 초기화 시 유실됨)
        subprocess.run(
            ["gsettings", "set", "org.freedesktop.ibus.engine.hangul",
             "switch-keys", "Hangul,Shift+space,Control+space"],
            capture_output=True, timeout=2,
        )
    except Exception:
        pass  # ibus 미설치 환경에서는 무시

from loguru import logger

from agent.core import Agent
from config import get_config

ROOT = Path(__file__).resolve().parent

CHARACTER_ID = "Haru"
WORLD_PATH   = ROOT / "conversation/world/W_sea.yaml"
SCENARIO_ID  = "morning_walk"
ACT_ID       = "act_1"


_PID_FILE = Path(tempfile.gettempdir()) / "achat.pid"


def _cleanup_previous() -> None:
    """이전 Achat 프로세스가 남아있으면 종료한다."""
    if not _PID_FILE.exists():
        return
    try:
        old_pid = int(_PID_FILE.read_text().strip())
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.TerminateProcess(
                ctypes.windll.kernel32.OpenProcess(1, False, old_pid), 1
            )
        else:
            os.kill(old_pid, signal.SIGTERM)
        logger.info(f"[startup] 이전 프로세스 종료 (PID {old_pid})")
    except (ProcessLookupError, ValueError, OSError):
        pass  # 이미 종료됨
    finally:
        _PID_FILE.unlink(missing_ok=True)


def _check_vram(min_free_mb: int = 3000) -> None:
    """CUDA 사용 가능 시 잔여 VRAM을 확인하고 부족하면 경고한다."""
    try:
        import torch
        if not torch.cuda.is_available():
            return
        free, total = torch.cuda.mem_get_info(0)
        free_mb  = free  // (1024 ** 2)
        total_mb = total // (1024 ** 2)
        logger.info(f"[VRAM] 여유: {free_mb} MB / {total_mb} MB")
        if free_mb < min_free_mb:
            logger.warning(
                f"[VRAM] 여유 메모리가 {min_free_mb} MB 미만입니다 ({free_mb} MB). "
                "이전 프로세스가 남아있을 수 있습니다. "
                "`nvidia-smi`로 확인 후 `kill -9 <PID>` 로 정리하세요."
            )
    except Exception:
        pass  # torch 미설치 환경(deploy)에서는 무시


def _inject_ibus_address() -> None:
    """IBUS_ADDRESS를 bus 파일에서 읽어 주입한다.
    이미 설정된 경우에도 소켓 파일 존재를 검증 — stale 주소면 갱신.
    """
    try:
        # 현재 값이 살아있는 소켓을 가리키는지 확인
        current = os.environ.get("IBUS_ADDRESS", "")
        if current:
            socket_path = next(
                (p[len("unix:path="):] for p in current.split(",")
                 if p.startswith("unix:path=")),
                None,
            )
            if socket_path and Path(socket_path).exists():
                return  # 유효한 소켓 — 그대로 사용

        # 소켓 없음 or IBUS_ADDRESS 미설정 → bus 파일에서 갱신
        machine_id = Path("/etc/machine-id").read_text().strip()
        display = os.environ.get("DISPLAY", ":0").lstrip(":").split(".")[0]
        bus_file = Path.home() / f".config/ibus/bus/{machine_id}-unix-{display}"
        if not bus_file.exists():
            wl = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
            bus_file = Path.home() / f".config/ibus/bus/{machine_id}-unix-{wl}"
        if bus_file.exists():
            for line in bus_file.read_text().splitlines():
                if line.startswith("IBUS_ADDRESS="):
                    os.environ["IBUS_ADDRESS"] = line.split("=", 1)[1]
                    break
    except Exception:
        pass


def main() -> None:
    # ── torch를 Qt보다 먼저 로드 (shared library 충돌 방지) ──────────────────
    _ensure_dbus_session()   # dbus 세션 버스 먼저 — ibus가 dbus로 통신
    _ensure_ibus_hangul()    # daemon 정상화 + bus 파일 갱신 (stale PID면 재시작)
    _inject_ibus_address()   # 갱신된 bus 파일에서 IBUS_ADDRESS 주입
    _cleanup_previous()
    _PID_FILE.write_text(str(os.getpid()))

    cfg = get_config()
    _check_vram()

    logger.info("Agent 초기화 중...")
    agent = Agent(
        character_id=CHARACTER_ID,
        world_path=str(WORLD_PATH),
        scenario_id=SCENARIO_ID,
        act_id=ACT_ID,
        config=cfg,
    )

    # ── Qt는 torch 로드 완료 후 import + 초기화 ──────────────────────────────
    from PySide6.QtWidgets import QApplication
    from ui_ux.tray import AppTrayIcon
    from ui_ux.widget import UIEngine

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    # QML 엔진 + 브리지
    ui = UIEngine(agent)

    # 앱 종료 직전 세션 저장
    app.aboutToQuit.connect(ui.bridge._sync_session_state)

    # 트레이 아이콘
    tray = AppTrayIcon(ui_engine=ui, bridge=ui.bridge)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
