#!/usr/bin/env python3
"""HarnessGenJ-dev Bootstrap — one-command setup and launch.

Usage:
    python bootstrap.py              # Install + start web dashboard
    python bootstrap.py --install-only  # Only install dependencies
    python bootstrap.py --start      # Skip install, just start

What it does:
    1. Detects Python 3.11+ and creates a venv (if not already in one)
    2. Installs harnessgenj-dev and all dependencies
    3. Guides API key configuration (env var or interactive prompt)
    4. Launches the web dashboard
"""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

# ---- Config ----
VENV_DIR = Path(__file__).resolve().parent / ".venv"
MIN_PYTHON = (3, 11)
REQUIREMENTS = ["-e", "."]

# ANSI colors
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def print_banner() -> None:
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════╗
║       HarnessGenJ-dev Bootstrap         ║
║   AI-driven multi-role dev assistant    ║
╚══════════════════════════════════════════╝{RESET}
""")


def check_python() -> bool:
    """Verify Python version."""
    v = sys.version_info[:2]
    if v < MIN_PYTHON:
        print(f"{RED}Error: Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required, found {v[0]}.{v[1]}{RESET}")
        return False
    print(f"{GREEN}✓ Python {v[0]}.{v[1]}{RESET}")
    return True


def setup_venv() -> Path | None:
    """Create venv if not running in one. Returns python path."""
    if sys.prefix != sys.base_prefix:
        print(f"{GREEN}✓ Already in virtual environment{RESET}")
        return Path(sys.executable)

    if VENV_DIR.exists():
        print(f"{YELLOW}→ Using existing .venv{RESET}")
    else:
        print(f"{CYAN}→ Creating virtual environment...{RESET}")
        venv.create(VENV_DIR, with_pip=True)

    if os.name == "nt":
        python = VENV_DIR / "Scripts" / "python.exe"
    else:
        python = VENV_DIR / "bin" / "python"

    if not python.exists():
        print(f"{RED}Error: venv python not found at {python}{RESET}")
        return None

    print(f"{GREEN}✓ Virtual environment ready{RESET}")
    return python


def install(python: Path) -> bool:
    """Install the package and dependencies."""
    print(f"{CYAN}→ Installing harnessgenj-dev and dependencies...{RESET}")
    try:
        subprocess.check_call(
            [str(python), "-m", "pip", "install", "-e", "."],
            cwd=Path(__file__).resolve().parent,
        )
        print(f"{GREEN}✓ Package installed{RESET}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"{RED}Error: pip install failed: {e}{RESET}")
        return False


def check_api_key() -> bool:
    """Check if API key is configured."""
    env_keys = [
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
    ]
    for k in env_keys:
        if os.environ.get(k, "").strip():
            print(f"{GREEN}✓ API key found: {k}{RESET}")
            return True

    settings_file = Path.home() / ".hgj-dev" / "web_settings.json"
    if settings_file.exists():
        try:
            import json
            settings = json.loads(settings_file.read_text(encoding="utf-8"))
            if settings.get("api_key", "").strip():
                print(f"{GREEN}✓ API key found in settings{RESET}")
                return True
        except Exception:
            pass

    print(f"""{YELLOW}
╔══════════════════════════════════════════╗
║  No API key detected.                   ║
║  Set one of these environment variables: ║
║    ANTHROPIC_API_KEY (Claude)           ║
║    OPENAI_API_KEY   (OpenAI/DeepSeek)   ║
║  Or configure in the web UI Settings tab.║
╚══════════════════════════════════════════╝{RESET}""")
    return True  # Not fatal — can configure in web UI


def launch(python: Path) -> None:
    """Launch the web dashboard."""
    print(f"{CYAN}→ Starting web dashboard on http://127.0.0.1:8000{RESET}")
    print(f"{CYAN}  Press Ctrl+C to stop{RESET}\n")
    os.chdir(Path(__file__).resolve().parent)
    os.execv(str(python), [str(python), "-m", "harnessgenj_dev.cli", "web"])


def main() -> None:
    print_banner()

    if not check_python():
        sys.exit(1)

    python = setup_venv()
    if python is None:
        sys.exit(1)

    if "--start" not in sys.argv:
        if not install(python):
            sys.exit(1)

    if "--install-only" in sys.argv:
        print(f"{GREEN}✓ Installation complete. Run 'python bootstrap.py --start' to launch.{RESET}")
        return

    check_api_key()
    launch(python)


if __name__ == "__main__":
    main()
