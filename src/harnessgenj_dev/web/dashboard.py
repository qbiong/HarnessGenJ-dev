"""Web Dashboard - FastAPI server with WebSocket streaming and REST APIs."""

from __future__ import annotations

import asyncio
import json
import subprocess
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ============================================================
# Settings Store
# ============================================================

_SETTINGS_FILE: Path = Path.home() / ".hgj-dev" / "web_settings.json"


def _load_settings() -> dict[str, Any]:
    if _SETTINGS_FILE.exists():
        try:
            with open(_SETTINGS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"provider": "deepseek", "model": "deepseek-v4-flash", "api_key": ""}


def _save_settings(settings: dict[str, Any]) -> None:
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def _get_api_key() -> str:
    settings = _load_settings()
    key = settings.get("api_key", "").strip()
    if key:
        return key
    return os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")


def _get_provider() -> str:
    settings = _load_settings()
    provider = settings.get("provider", "").strip()
    if provider:
        return provider
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return "openai"
    return "deepseek"


def _get_model() -> str:
    settings = _load_settings()
    custom = settings.get("model_custom", "").strip()
    if custom:
        return custom
    model = settings.get("model", "").strip()
    if model:
        return model
    return "deepseek-v4-flash"


def _get_base_url() -> str:
    settings = _load_settings()
    return settings.get("base_url", "").strip()


def _get_proj_path() -> str | None:
    """Get active project root path."""
    try:
        from harnessgenj_dev.projects import get_active_project
        active = get_active_project()
        return active["path"] if active else None
    except Exception:
        return None


def _has_api_key() -> bool:
    return bool(_get_api_key())


def _get_system_metrics() -> dict[str, Any]:
    import platform

    return {
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "cwd": os.getcwd(),
        "uptime_seconds": time.time() - _start_time,
    }


_start_time = time.time()

# ===========================================================================
# Unified SPA Dashboard
# ===========================================================================


def _get_dashboard_html(active_tab: str = "chat", settings_data: dict | None = None) -> str:
    """Return the single-page application HTML for the dashboard.

    Args:
        active_tab: Default active tab ('chat', 'projects', 'files', 'settings').
        settings_data: Pre-loaded settings (None = fetch from API on client-side).
    """
    has_key = _has_api_key()
    provider = _get_provider()
    model = _get_model()

    # Build settings JSON for client-side use
    if settings_data is None:
        settings_data = _load_settings()
    settings_json = json.dumps(settings_data, ensure_ascii=False)

    model_custom = settings_data.get("model_custom", "")
    effective_model = model_custom if model_custom else settings_data.get("model", "deepseek-v4-flash")

    has_env_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    has_env_openai = bool(os.environ.get("OPENAI_API_KEY", "").strip())

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HGJ-dev</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
    --bg-primary: #0a0e14; --bg-secondary: #131920; --bg-tertiary: #1a2230;
    --accent-cyan: #00d4ff; --accent-purple: #a855f7; --accent-blue: #3b82f6;
    --success: #10b981; --warning: #f59e0b; --error: #ef4444;
    --text-primary: #e2e8f0; --text-secondary: #94a3b8; --text-muted: #64748b;
    --border: #1e293b; --border-light: #263348;
    --font-mono: 'JetBrains Mono','Fira Code',monospace;
    --font-sans: 'Outfit',system-ui,sans-serif;
    --radius-sm: 6px; --radius-md: 10px; --radius-lg: 16px;
    --shadow-card: 0 4px 24px rgba(0,0,0,0.4);
    --transition: 0.2s ease;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: var(--font-sans);
    background: var(--bg-primary);
    color: var(--text-primary);
    height: 100vh; display: flex; flex-direction: column;
    background-image: radial-gradient(ellipse at 20% 0%, rgba(0,212,255,0.08) 0%, transparent 50%),
                      radial-gradient(ellipse at 80% 100%, rgba(168,85,247,0.06) 0%, transparent 50%);
}}

/* Top Nav */
.topnav {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 24px; height: 52px;
    background: linear-gradient(180deg, rgba(19,25,32,0.98) 0%, rgba(19,25,32,0.9) 100%);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    position: sticky; top: 0; z-index: 50;
}}
.topnav::after {{
    content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent-cyan), transparent); opacity: 0.4;
}}
.topnav-brand {{
    font-size: 17px; font-weight: 700;
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; letter-spacing: -0.5px;
}}
.topnav-tabs {{ display: flex; gap: 4px; }}
.topnav-tab {{
    padding: 8px 16px; font-size: 13px; font-weight: 500;
    color: var(--text-muted); text-decoration: none; cursor: pointer;
    border-radius: var(--radius-sm); transition: all var(--transition);
    font-family: var(--font-sans);
}}
.topnav-tab:hover {{ color: var(--text-primary); background: var(--bg-tertiary); }}
.topnav-tab.active {{ color: var(--accent-cyan); background: rgba(0,212,255,0.1); }}
.topnav-right {{ display: flex; align-items: center; gap: 12px; }}

/* Status dot */
.status-dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
.status-dot.idle {{ background: var(--success); }}
.status-dot.running {{ background: var(--success); box-shadow: 0 0 12px rgba(16,185,129,0.5); animation: pulse 1s infinite; }}
.status-dot.error {{ background: var(--error); }}
@keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}

/* Main area */
.main {{
    flex: 1; display: flex; overflow: hidden;
}}

/* Section display */
.tab-section {{ display: none; width: 100%; height: 100%; overflow-y: auto; overflow-x: hidden; }}
.tab-section.active {{ display: flex; flex-direction: column; }}

/* ============ Chat View ============ */
.chat-container {{ flex: 1; display: flex; flex-direction: column; width: 100%; overflow: hidden; }}
.chat-messages {{ flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }}
.welcome {{ text-align: center; padding: 60px 20px; }}
.welcome h2 {{ font-size: 24px; background: linear-gradient(135deg,var(--accent-cyan),var(--accent-purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }}
.welcome p {{ color: var(--text-secondary); margin-top: 8px; font-size: 13px; }}
.chat-input-area {{ padding: 12px 20px 16px; border-top: 1px solid var(--border); background: var(--bg-primary); position: sticky; bottom: 0; z-index: 41; }}
.chat-input-row {{ display: flex; gap: 8px; align-items: flex-end; }}
.chat-input {{
    flex: 1; resize: none; padding: 10px 14px; border-radius: var(--radius-md);
    border: 1px solid var(--border); background: var(--bg-secondary);
    color: var(--text-primary); font-family: var(--font-mono); font-size: 13px;
    outline: none; transition: border var(--transition); min-height: 42px; max-height: 120px;
}}
.chat-input:focus {{ border-color: var(--accent-cyan); }}
.btn {{
    padding: 8px 18px; border-radius: var(--radius-sm); border: none;
    font-size: 12px; font-weight: 600; cursor: pointer; font-family: var(--font-sans);
    transition: all var(--transition); white-space: nowrap;
}}
.btn-send {{ background: var(--accent-cyan); color: #000; }}
.btn-send:hover {{ box-shadow: 0 0 16px rgba(0,212,255,0.3); }}
.btn-stop {{ background: var(--error); color: white; }}
.btn-stop:hover {{ opacity: 0.9; }}
.btn-secondary {{ background: var(--bg-tertiary); color: var(--text-secondary); border: 1px solid var(--border); }}
.btn-secondary:hover {{ color: var(--text-primary); border-color: var(--accent-cyan); }}

/* Messages */
/* Messages — avatar left/right, bubble auto-width */.msg-group {{ display: flex; align-items: flex-start; gap: 10px; margin: 14px 0; animation: msgSlide 0.2s ease-out; }}
@keyframes msgSlide {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: translateY(0); }} }}
.msg-group.user {{ flex-direction: row-reverse; }}
.msg-group.system {{ justify-content: center; }}
.msg-avatar {{ width: 32px; height: 32px; min-width: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; box-shadow: 0 2px 6px rgba(0,0,0,0.2); }}
.msg-avatar.pjm {{ background: linear-gradient(135deg, #f59e0b22, #f59e0b44); color: #fbbf24; border: 1px solid #f59e0b33; }}
.msg-avatar.pm {{ background: linear-gradient(135deg, #00d4ff22, #00d4ff44); color: #00d4ff; border: 1px solid #00d4ff33; }}
.msg-avatar.pdm {{ background: linear-gradient(135deg, #00d4ff22, #00d4ff44); color: #00d4ff; border: 1px solid #00d4ff33; }}
.msg-avatar.arch {{ background: linear-gradient(135deg, #3b82f622, #3b82f644); color: #60a5fa; border: 1px solid #3b82f633; }}
.msg-avatar.dev {{ background: linear-gradient(135deg, #10b98122, #10b98144); color: #34d399; border: 1px solid #10b98133; }}
.msg-avatar.rev {{ background: linear-gradient(135deg, #f0883e22, #f0883e44); color: #fbbf24; border: 1px solid #f0883e33; }}
.msg-avatar.hunt {{ background: linear-gradient(135deg, #ef444422, #ef444444); color: #f87171; border: 1px solid #ef444433; }}
.msg-avatar.doc {{ background: linear-gradient(135deg, #94a3b822, #94a3b844); color: #cbd5e1; border: 1px solid #94a3b833; }}
.msg-avatar.user {{ background: linear-gradient(135deg, #a855f722, #a855f744); color: #c084fc; border: 1px solid #a855f733; }}
.msg-body {{ max-width: 75%; }}
.msg-sender {{ font-size: 10px; font-weight: 600; margin-bottom: 3px; padding-left: 2px; letter-spacing: 0.2px; }}
.msg-sender.pjm {{ color: #fbbf24; }}
.msg-sender.pm {{ color: #00d4ff; }}
.msg-sender.pdm {{ color: #00d4ff; }}
.msg-sender.arch {{ color: #60a5fa; }}
.msg-sender.dev {{ color: #34d399; }}
.msg-sender.rev {{ color: #fbbf24; }}
.msg-sender.hunt {{ color: #f87171; }}
.msg-sender.doc {{ color: #94a3b8; }}
.msg-bubble {{ display: inline-block; padding: 10px 14px; border-radius: 12px; font-size: 13px; line-height: 1.6; background: linear-gradient(135deg, rgba(19,25,32,0.9), rgba(26,34,48,0.8)); border: 1px solid rgba(255,255,255,0.06); box-shadow: 0 1px 6px rgba(0,0,0,0.12); }}

/* ============ Session Panel ============ */
.role-select {{ background: var(--bg-tertiary); color: var(--text-secondary); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 4px 8px; font-size: 11px; font-family: var(--font-mono); outline: none; }}
.role-select:focus {{ border-color: var(--accent-cyan); }}
.session-dropdown {{ position: relative; display: inline-block; }}
.session-bar {{ display: flex; align-items: center; gap: 8px; padding: 8px 20px; background: var(--bg-secondary); border-bottom: 1px solid var(--border); font-size: 12px; position: sticky; top: 0; z-index: 42; flex-shrink: 0; }}
.session-panel {{ display: none; position: fixed; top: 100px; right: 20px; background: rgba(19,25,32,0.97); backdrop-filter: blur(16px); border: 1px solid var(--border); border-radius: var(--radius-md); min-width: 320px; max-width: calc(100vw - 40px); max-height: calc(100vh - 120px); overflow-y: auto; box-shadow: var(--shadow-card); z-index: 100; }}
.session-panel.open {{ display: block; }}
.session-panel-header {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--bg-secondary); z-index: 1; }}
.session-panel-header span {{ font-size: 12px; font-weight: 600; color: var(--text-primary); }}
.session-panel-header button {{ background: var(--success); color: white; border: none; border-radius: var(--radius-sm); padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer; }}
.session-item {{ padding: 10px 14px; cursor: pointer; border-bottom: 1px solid var(--border); transition: background var(--transition); }}
.session-item:hover {{ background: var(--bg-tertiary); }}
.session-item.active {{ background: linear-gradient(90deg, rgba(16,185,129,0.15), transparent); border-left: 3px solid var(--success); }}
.session-item .s-title {{ font-size: 12px; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.session-item .s-meta {{ font-size: 10px; color: var(--text-muted); margin-top: 3px; }}
.session-item .s-actions {{ display: inline-block; margin-left: 8px; }}
.session-item .s-actions a {{ color: var(--error); font-size: 10px; cursor: pointer; text-decoration: none; }}
.msg-bubble code {{ background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; font-size: 12px; color: #e06c75; }}
.msg-bubble pre {{ background: rgba(0,0,0,0.3); padding: 10px; border-radius: 6px; overflow-x: auto; font-size: 12px; margin: 6px 0; border: 1px solid rgba(255,255,255,0.04); }}
.msg-group:not(.user) .msg-bubble {{ border-color: rgba(0,212,255,0.08); }}
.msg-group.user .msg-bubble {{ border-color: rgba(168,85,247,0.15); }}
/* Thinking block — DeepSeek-style collapsible reasoning */
.thinking-block {{ margin: 2px 42px 6px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; font-size: 11px; color: var(--text-muted); overflow: hidden; }}
.thinking-header {{ padding: 6px 10px; cursor: pointer; user-select: none; font-size: 11px; color: var(--text-muted); display: flex; align-items: center; gap: 4px; }}
.thinking-header:hover {{ color: var(--text-secondary); background: rgba(255,255,255,0.02); }}
.thinking-content {{ padding: 8px 10px; border-top: 1px solid var(--border); white-space: pre-wrap; font-size: 11px; line-height: 1.5; max-height: 400px; overflow-y: auto; color: var(--text-secondary); }}
/* Tool call card */
.tool-card {{ align-self: flex-start; background: var(--bg-tertiary); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 8px 12px; max-width: 70%; margin: 4px 0; font-size: 12px; }}
.tool-card .tc-name {{ color: var(--accent-cyan); font-weight: 600; font-size: 11px; }}
.tool-card .tc-status {{ color: var(--text-muted); font-size: 11px; }}
.tool-card .tc-result {{ color: var(--text-secondary); font-size: 11px; margin-top: 4px; white-space: pre-wrap; }}

/* ============ Projects View ============ */
.projects-container {{ padding: 24px; max-width: 800px; width: 100%; margin: 0 auto; }}
.projects-container h2 {{ font-size: 18px; color: var(--accent-cyan); margin-bottom: 16px; }}
.projects-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
.projects-table th, .projects-table td {{ border: 1px solid var(--border); padding: 8px 12px; text-align: left; }}
.projects-table th {{ background: var(--bg-secondary); color: var(--accent-cyan); font-weight: 600; }}
.projects-table tr:nth-child(even) {{ background: var(--bg-secondary); }}
.add-project-row {{ display: flex; gap: 8px; margin-top: 12px; align-items: center; }}
.add-project-row input {{
    padding: 6px 10px; border-radius: var(--radius-sm);
    border: 1px solid var(--border); background: var(--bg-primary);
    color: var(--text-primary); font-family: var(--font-mono); font-size: 12px;
}}

/* ============ Files View ============ */
.files-container {{ padding: 24px; width: 100%; margin: 0 auto; }}
.files-container h2 {{ font-size: 18px; color: var(--accent-cyan); margin-bottom: 16px; }}
.files-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
.files-table th, .files-table td {{ border: 1px solid var(--border); padding: 8px 12px; text-align: left; }}
.files-table th {{ background: var(--bg-secondary); color: var(--accent-cyan); }}
.files-table tr:nth-child(even) {{ background: var(--bg-secondary); }}
.file-viewer {{ background: #0a0e14; padding: 14px; border-radius: var(--radius-md); margin-top: 12px; white-space: pre-wrap; font-family: var(--font-mono); font-size: 12px; overflow-x: auto; max-height: 400px; display: none; }}

/* ============ Settings View ============ */
.settings-container {{ padding: 24px; max-width: 640px; width: 100%; margin: 0 auto; }}
.settings-container h2 {{ font-size: 18px; color: var(--accent-cyan); margin-bottom: 16px; }}
.settings-section {{ background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 20px; margin-bottom: 16px; }}
.settings-section h3 {{ font-size: 13px; color: var(--text-primary); margin-bottom: 14px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }}
.settings-label {{ display: block; color: var(--text-secondary); font-size: 12px; margin-bottom: 4px; }}
.settings-input {{
    width: 100%; padding: 8px 12px; border-radius: var(--radius-sm);
    border: 1px solid var(--border); background: var(--bg-primary);
    color: var(--text-primary); font-family: var(--font-mono); font-size: 13px;
    margin-bottom: 14px; outline: none;
}}
.settings-input:focus {{ border-color: var(--accent-cyan); }}
.settings-select {{ composes: settings-input; }}
.settings-hint {{ font-size: 11px; color: var(--text-muted); margin-top: -10px; margin-bottom: 14px; }}
.settings-btns {{ display: flex; gap: 10px; }}
.status-box {{ padding: 10px 14px; border-radius: var(--radius-sm); margin-bottom: 14px; font-size: 13px; }}
.status-box.ok {{ background: #122d1c; border: 1px solid var(--success); color: var(--success); }}
.status-box.warn {{ background: #2d2212; border: 1px solid var(--warning); color: var(--warning); }}

/* ============ File Link in Chat ============ */
.file-link {{
    color: var(--accent-cyan); cursor: pointer; text-decoration: underline;
    text-decoration-style: dotted; text-underline-offset: 3px;
    transition: all var(--transition);
}}
.file-link:hover {{ color: #fff; text-decoration-style: solid; }}

/* ============ File Viewer Modal ============ */
.file-modal-overlay {{
    display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0,0,0,0.7); z-index: 200; align-items: center; justify-content: center;
}}
.file-modal-overlay.open {{ display: flex; }}
.file-modal {{
    background: var(--bg-secondary); border: 1px solid var(--border);
    border-radius: var(--radius-lg); width: 85vw; max-width: 900px;
    max-height: 80vh; display: flex; flex-direction: column;
    box-shadow: 0 8px 48px rgba(0,0,0,0.6);
}}
.file-modal-header {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 20px; border-bottom: 1px solid var(--border);
    font-family: var(--font-mono); font-size: 12px; flex-shrink: 0;
}}
.file-modal-header .fm-path {{ color: var(--accent-cyan); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.file-modal-header .fm-close {{
    background: none; border: none; color: var(--text-muted); font-size: 20px;
    cursor: pointer; padding: 0 4px; line-height: 1;
}}
.file-modal-header .fm-close:hover {{ color: var(--text-primary); }}
.file-modal-body {{
    flex: 1; overflow: auto; padding: 16px 20px;
    font-family: var(--font-mono); font-size: 12px; line-height: 1.7;
    white-space: pre-wrap; color: var(--text-primary);
    background: #0a0e14;
}}
.file-modal-body.loading {{ color: var(--text-muted); text-align: center; padding: 40px; }}
.file-modal-body.error {{ color: var(--error); }}
.file-modal-body.md-rendered {{
    white-space: normal; font-family: var(--font-sans); font-size: 13px;
    line-height: 1.8; padding: 20px 24px; background: var(--bg-primary);
}}
.file-modal-body.md-rendered h1 {{ font-size: 1.6em; border-bottom: 1px solid var(--border); padding-bottom: 8px; margin: 16px 0 12px; }}
.file-modal-body.md-rendered h2 {{ font-size: 1.3em; margin: 14px 0 10px; color: var(--accent-cyan); }}
.file-modal-body.md-rendered h3 {{ font-size: 1.1em; margin: 12px 0 8px; }}
.file-modal-body.md-rendered p {{ margin: 6px 0; }}
.file-modal-body.md-rendered code {{ background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; font-size: 0.9em; color: #e06c75; }}
.file-modal-body.md-rendered pre {{ background: rgba(0,0,0,0.3); padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 0.85em; margin: 8px 0; }}
.file-modal-body.md-rendered table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
.file-modal-body.md-rendered th, .file-modal-body.md-rendered td {{ border: 1px solid var(--border); padding: 6px 10px; text-align: left; font-size: 0.9em; }}
.file-modal-body.md-rendered th {{ background: var(--bg-secondary); color: var(--accent-cyan); }}
.file-modal-body.md-rendered ul, .file-modal-body.md-rendered ol {{ padding-left: 20px; margin: 6px 0; }}
.file-modal-body.md-rendered blockquote {{ border-left: 3px solid var(--accent-cyan); padding-left: 12px; color: var(--text-secondary); margin: 8px 0; }}
.file-modal-body.md-rendered a {{ color: var(--accent-cyan); }}
.file-modal-body.md-rendered hr {{ border: none; border-top: 1px solid var(--border); margin: 12px 0; }}
.file-modal-footer {{
    padding: 8px 20px; border-top: 1px solid var(--border);
    font-size: 10px; color: var(--text-muted); flex-shrink: 0;
    display: flex; justify-content: space-between;
}}
/* Session ID badge */
.session-id-badge {{
    font-family: var(--font-mono); font-size: 9px; color: var(--text-muted);
    background: var(--bg-primary); padding: 1px 6px; border-radius: 3px;
    margin-left: 6px; cursor: pointer; user-select: all;
}}
.session-id-badge:hover {{ color: var(--accent-cyan); }}
</style>
</head>
<body>

<!-- Top Navigation -->
<nav class="topnav">
    <div class="topnav-brand">HGJ-dev</div>
    <span style="flex:1"></span>
    <div class="topnav-tabs">
        <a class="topnav-tab{" active" if active_tab == "chat" else ""}" onclick="switchTab('chat')">对话</a>
        <a class="topnav-tab{" active" if active_tab == "projects" else ""}" onclick="switchTab('projects')">项目</a>
        <a class="topnav-tab{" active" if active_tab == "files" else ""}" onclick="switchTab('files')">文件</a>
        <a class="topnav-tab{" active" if active_tab == "roles" else ""}" onclick="switchTab('roles')">角色</a>
        <a class="topnav-tab{" active" if active_tab == "settings" else ""}" onclick="switchTab('settings')">设置</a>
    </div>
    <div class="topnav-right">
        <span class="status-dot idle" id="status-dot"></span>
        <span style="font-size:11px;color:var(--text-muted)" id="status-text">就绪</span>
        <span style="font-size:11px;color:var(--text-muted)" id="iter-info"></span>
    </div>
</nav>

<!-- Main Content -->
<div class="main">

<!-- ===== Chat Section ===== -->
<div class="tab-section{" active" if active_tab == "chat" else ""}" id="tab-chat">
    <div class="session-bar">
        <select class="role-select" id="project-select" onchange="switchActiveProject()">
            <option value="">加载中...</option>
        </select>
        <span style="font-size:11px;color:var(--text-muted)">|</span>
        <span style="font-size:11px;color:var(--accent-cyan);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:300px;" id="project-info"></span>
        <span style="font-size:11px;color:var(--text-muted)">|</span>
        <span style="font-size:11px;color:var(--text-muted)">|</span>
        <span style="font-size:10px;color:var(--text-muted);font-family:var(--font-mono);" id="current-session-id" title="当前会话ID"></span>
        <select class="role-select" id="role-select" style="display:none;"><option value="project_manager" selected>Project Manager</option></select>
        <span style="font-size:11px;color:var(--text-muted)" id="key-info"></span>
        <span style="flex:1"></span>
        <div class="session-dropdown">
            <a style="font-size:12px;color:var(--text-secondary);cursor:pointer;text-decoration:none;" onclick="toggleSessionPanel()">会话</a>
            <div id="session-panel" class="session-panel">
                <div class="session-panel-header">
                    <span>会话列表</span>
                    <button onclick="newSession()">+ 新建</button>
                </div>
                <div id="session-list"></div>
            </div>
        </div>
    </div>

    <div class="chat-container">
        <div class="chat-messages" id="chat">
            <div class="welcome" id="welcome">
                <h2>HGJ-dev</h2>
                <p>AI 驱动的多角色开发助手</p>
                <p style="margin-top:8px;font-size:12px;color:var(--text-muted);">输入请求，项目经理将自动调度团队完成任务</p>
                <div id="no-api-key-hint" style="display:none;margin-top:12px;padding:10px 16px;background:var(--bg-secondary);border:1px solid var(--error);border-radius:var(--radius-sm);font-size:12px;color:var(--text-secondary);">
                    🔑 尚未配置 API Key。请先 <a href=\"javascript:switchTab('settings')\" style=\"color:var(--accent-cyan);\">在设置中配置</a>，或设置环境变量 <code style=\"color:var(--accent-cyan);\">ANTHROPIC_API_KEY</code>
                </div>
                <div id="no-project-hint" style="display:none;margin-top:12px;padding:10px 16px;background:var(--bg-secondary);border:1px solid var(--warning);border-radius:var(--radius-sm);font-size:12px;color:var(--text-secondary);">
                    🚀 尚未配置项目。请先 <a href=\"javascript:switchTab('projects')\" style=\"color:var(--accent-cyan);\">添加项目</a> 或直接告诉 AI 你的项目路径
                </div>
            </div>
        </div>
        <div class="chat-input-area">
            <div class="chat-input-row">
                <textarea class="chat-input" id="msg-input" placeholder="描述你想要实现的功能..." rows="1"></textarea>
                <button class="btn btn-send" id="btn-send" onclick="send()">发送</button>
                <button class="btn btn-stop" id="btn-stop" onclick="interrupt()" style="display:none;">停止</button>
            </div>
        </div>
    </div>
</div>

<!-- ===== Projects Section ===== -->
<div class="tab-section{" active" if active_tab == "projects" else ""}" id="tab-projects">
    <div class="projects-container">
        <h2>项目列表</h2>
        <div id="projects-list"></div>
        <!-- New Workspace Project -->
        <div class="add-project-row" style="margin-top:16px;padding-top:12px;border-top:1px solid var(--border);">
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                <div style="flex:1;min-width:150px;">
                    <div style="font-size:11px;color:var(--text-secondary);margin-bottom:4px;">新建项目</div>
                    <input id="pname" placeholder="项目名称" style="width:100%;" />
                </div>
                <div style="flex:2;min-width:200px;">
                    <div style="font-size:11px;color:var(--text-secondary);margin-bottom:4px;">描述 (可选，可由AI自动生成)</div>
                    <input id="pdesc" placeholder="项目描述" style="width:100%;" />
                </div>
                <div style="flex:1;min-width:200px;">
                    <div style="font-size:11px;color:var(--text-secondary);margin-bottom:4px;">GitHub URL (可选)</div>
                    <input id="pgithub" placeholder="https://github.com/user/repo" style="width:100%;" />
                </div>
                <button class="btn btn-send" onclick="addProject()" style="align-self:flex-end;margin-bottom:1px;">新建</button>
            </div>
            <div style="font-size:10px;color:var(--text-muted);margin-top:4px;">不填路径将自动在 workspace 目录中创建</div>
        </div>
        <!-- Open External Project -->
        <div class="add-project-row" style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border);">
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                <div style="flex:1;min-width:150px;">
                    <input id="epname" placeholder="项目名称" style="width:100%;" />
                </div>
                <div style="flex:2;min-width:200px;">
                    <input id="eppath" placeholder="已存在的项目路径 (必填)" style="width:100%;" />
                </div>
                <div style="flex:2;min-width:200px;">
                    <input id="epdesc" placeholder="描述 (可选)" style="width:100%;" />
                </div>
                <div style="flex:1;min-width:200px;">
                    <input id="epgithub" placeholder="GitHub URL (可选)" style="width:100%;" />
                </div>
                <button class="btn btn-secondary" onclick="addExternalProject()" style="align-self:flex-end;margin-bottom:1px;">打开外部项目</button>
            </div>
        </div>
    </div>
</div>

<!-- ===== Files Section ===== -->
<div class="tab-section{" active" if active_tab == "files" else ""}" id="tab-files">
    <div class="files-container">
        <h2>文件浏览器</h2>
        <div id="file-listing"></div>
        <pre class="file-viewer" id="file-viewer"></pre>
    </div>
</div>

<!-- ===== Settings Section ===== -->
<div class="tab-section{" active" if active_tab == "roles" else ""}" id="tab-roles">
    <div class="settings-container">
        <h2>角色配置与新增</h2>
        <div class="settings-section">
            <h3>当前团队角色</h3>
            <div id="roles-list" style="display:flex;flex-wrap:wrap;gap:12px;margin-bottom:20px;"></div>
        </div>
        <div class="settings-section">
            <h3>新增自定义角色</h3>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;max-width:600px;">
                <div><label class="settings-label">角色ID (英文)</label><input class="settings-input" id="new-role-id" placeholder="e.g. security_auditor"></div>
                <div><label class="settings-label">显示名称</label><input class="settings-input" id="new-role-name" placeholder="e.g. 安全审计员"></div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;max-width:600px;margin-top:8px;">
                <div><label class="settings-label">头像缩写 (2-3字符)</label><input class="settings-input" id="new-role-avatar" placeholder="e.g. SA" maxlength="3"></div>
                <div><label class="settings-label">颜色标识</label><select class="settings-input" id="new-role-color"><option value="pjm">金黄</option><option value="pm">紫色</option><option value="arch">青色</option><option value="dev">蓝色</option><option value="rev">绿色</option><option value="hunt">红色</option><option value="doc">灰色</option></select></div>
            </div>
            <div style="margin-top:8px;"><label class="settings-label">角色描述</label><input class="settings-input" id="new-role-desc" placeholder="这个角色负责什么"></div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:8px;">
                <div><label class="settings-label">可以做什么 (每行一项)</label><textarea class="settings-input" id="new-role-can" rows="4" placeholder="分析安全漏洞
执行渗透测试
编写安全报告"></textarea></div>
                <div><label class="settings-label">不能做什么 (每行一项)</label><textarea class="settings-input" id="new-role-cannot" rows="4" placeholder="修改代码
调度其他角色"></textarea></div>
            </div>
            <button class="btn btn-send" onclick="addRole()" style="margin-top:12px;">创建角色并初始化记忆空间</button>
            <span id="roles-status" style="color:var(--accent-cyan);margin-left:12px;font-size:13px;"></span>
        </div>
    </div>
</div>

<div class="tab-section{" active" if active_tab == "settings" else ""}" id="tab-settings">
    <div class="settings-container">
        <h2>设置</h2>
        <div id="settings-status"></div>
        <div class="settings-section">
            <h3>LLM 配置</h3>
            <label class="settings-label">提供商</label>
            <select class="settings-input" id="s-provider">
                <optgroup label="International">
                    <option value="anthropic">Anthropic (Claude)</option>
                    <option value="openai">OpenAI (GPT)</option>
                    <option value="openrouter">OpenRouter</option>
                </optgroup>
                <optgroup label="China">
                    <option value="deepseek">DeepSeek</option>
                    <option value="qwen">通义千问 (Qwen)</option>
                    <option value="zhipu">智谱 AI (GLM)</option>
                    <option value="moonshot">月之暗面 (Moonshot)</option>
                    <option value="siliconflow">SiliconFlow</option>
                    <option value="custom">Custom</option>
                </optgroup>
            </select>
            <label class="settings-label">模型 (下拉选择)</label>
            <select class="settings-input" id="s-model"></select>
            <label class="settings-label">
                模型 (自定义)
                <span style="color:var(--accent-cyan);font-size:11px;">← 优先</span>
            </label>
            <input class="settings-input" id="s-model-custom" placeholder="例如 deepseek-v4-flash" />
            <div class="settings-hint">若填写则优先于下拉选择</div>
            <label class="settings-label">API 地址 (可选)</label>
            <input class="settings-input" id="s-base-url" placeholder="例如 https://api.deepseek.com" />
            <label class="settings-label">API 密钥</label>
            <input class="settings-input" type="password" id="s-api-key" autocomplete="off" />
            <label class="settings-label">角色对我的称呼</label>
            <input class="settings-input" id="s-user-title" placeholder="例如：老板、用户、开发者" />
            <div class="settings-hint">所有AI角色在与您交流时使用此称呼。默认：用户</div>
            <div class="settings-btns">
                <button class="btn btn-send" onclick="saveSettings()">保存</button>
                <button class="btn btn-secondary" onclick="clearSettings()">清除</button>
                <button class="btn btn-secondary" onclick="testConnection()">测试连接</button>
            </div>
        </div>
        <div class="settings-section">
            <h3>当前状态</h3>
            <div style="font-size:13px;color:var(--text-secondary);">
                <p>提供商: <span id="s-current-provider" style="color:var(--text-primary);">{provider}</span></p>
                <p style="margin-top:6px;">模型: <span id="s-current-model" style="color:var(--text-primary);">{effective_model}</span></p>
                <p style="margin-top:6px;">API 密钥: <span id="s-current-key" style="color:var(--text-primary);">{"sk-" + _get_api_key()[:6] + "..." if _get_api_key() else "未设置"}</span></p>
            </div>
        </div>
    </div>
</div>

</div><!-- /main -->

<script>
// ---- Settings data injected from backend ----
var SETTINGS = {settings_json};
var ACTIVE_TAB = '{active_tab}';

// ---- Tab Switching ----
function switchTab(tab) {{
    document.querySelectorAll('.tab-section').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.topnav-tab').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + tab).classList.add('active');
    document.querySelectorAll('.topnav-tab').forEach(el => {{
        if (el.textContent.trim() === ['对话','项目','文件','角色','设置'][['chat','projects','files','roles','settings'].indexOf(tab)]) el.classList.add('active');
    }});
    if (tab === 'projects') loadProjects();
    if (tab === 'files') listDir('');
    if (tab === 'roles') loadRoles();
}}
// Support hash-based deep links
var tabFromHash = {{'#chat':'chat','#projects':'projects','#files':'files','#roles':'roles','#settings':'settings'}}[location.hash];
if (tabFromHash) switchTab(tabFromHash);

// ---- Role Management ----
async function loadRoles() {{
    try {{
        var r = await fetch('/api/roles');
        var data = await r.json();
        var el = document.getElementById('roles-list');
        el.innerHTML = data.roles.map(function(role) {{
            var colorMap = {{'pjm':'#fbbf24','pm':'#a855f7','arch':'#00d4ff','dev':'#3b82f6','rev':'#10b981','hunt':'#ef4444','doc':'#94a3b8'}};
            var bgColor = colorMap[role.color] || '#94a3b8';
            var isBuiltin = role.builtin ? ' (内置)' : '';
            var canList = (role.can_do || []).slice(0,3).join(', ');
            var cannotList = (role.must_not || []).slice(0,2).join(', ');
            var deleteBtn = role.builtin ? '' : '<button onclick=\"deleteRole(\\'' + role.id + '\\')\" style=\"background:var(--error);color:#fff;border:none;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:11px;\">删除</button>';
            var coordinator = role.is_coordinator ? '<span style=\"font-size:10px;background:var(--accent-cyan);color:#000;padding:1px 6px;border-radius:3px;margin-left:4px;\">协调者</span>' : '';
            var dispatchTarget = data.dispatch_targets.includes(role.id) ? '<span style=\"font-size:10px;background:rgba(16,185,129,0.2);color:var(--success);padding:1px 6px;border-radius:3px;margin-left:4px;\">可调度</span>' : '';
            return '<div style=\"background:var(--bg-secondary);border:1px solid var(--border);border-radius:var(--radius-md);padding:14px;min-width:260px;flex:1;\">' +
                '<div style=\"display:flex;align-items:center;gap:8px;margin-bottom:8px;\">' +
                '<div style=\"width:36px;height:36px;border-radius:50%;background:' + bgColor + '22;color:' + bgColor + ';display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;border:1px solid ' + bgColor + '44;\">' + (role.avatar || role.id.substring(0,2).toUpperCase()) + '</div>' +
                '<div><strong>' + role.display_name + '</strong>' + isBuiltin + coordinator + dispatchTarget + '<br><code style=\"font-size:10px;color:var(--text-muted);\">@' + role.id + '</code></div>' +
                deleteBtn + '</div>' +
                '<div style=\"font-size:11px;color:var(--text-secondary);margin-bottom:4px;\">' + (role.description || '') + '</div>' +
                '<div style=\"font-size:10px;color:var(--success);\">✓ ' + (canList || '无') + '</div>' +
                '<div style=\"font-size:10px;color:var(--error);\">✗ ' + (cannotList || '无') + '</div>' +
                '</div>';
        }}).join('');
    }} catch(e) {{ console.error(e); }}
}}

async function addRole() {{
    var roleId = document.getElementById('new-role-id').value.trim();
    if (!roleId) {{ alert('请输入角色ID'); return; }}
    var body = {{
        id: roleId,
        display_name: document.getElementById('new-role-name').value.trim() || roleId,
        avatar: document.getElementById('new-role-avatar').value.trim() || roleId.substring(0,2).toUpperCase(),
        color: document.getElementById('new-role-color').value,
        description: document.getElementById('new-role-desc').value.trim(),
        can_do: document.getElementById('new-role-can').value.trim(),
        must_not: document.getElementById('new-role-cannot').value.trim(),
    }};
    try {{
        var r = await fetch('/api/roles', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(body)}});
        var data = await r.json();
        if (data.status === 'created') {{
            document.getElementById('roles-status').textContent = '✓ 角色 ' + roleId + ' 已创建，记忆空间: ' + data.memory_path;
            document.getElementById('new-role-id').value = '';
            document.getElementById('new-role-name').value = '';
            loadRoles();
        }} else {{
            document.getElementById('roles-status').textContent = '错误: ' + JSON.stringify(data);
        }}
    }} catch(e) {{
        document.getElementById('roles-status').textContent = '错误: ' + e.message;
    }}
}}

async function deleteRole(roleId) {{
    if (!confirm('确定删除角色 ' + roleId + '？')) return;
    try {{
        await fetch('/api/roles/' + roleId, {{method:'DELETE'}});
        loadRoles();
    }} catch(e) {{ console.error(e); }}
}}

// ---- Session Panel ----
function toggleSessionPanel() {{
    document.getElementById('session-panel').classList.toggle('open');
}}

document.addEventListener('click', function(e) {{
    var panel = document.getElementById('session-panel');
    if (!panel) return;
    var inside = e.target.closest('.session-dropdown');
    if (!inside && panel.classList.contains('open')) {{
        panel.classList.remove('open');
    }}
}});

// ---- WebSocket Connection ----
var ws = null;
var currentSessionId = null;
var roleSelect = document.getElementById('role-select');
var chat = document.getElementById('chat');
var msgInput = document.getElementById('msg-input');
var btnSend = document.getElementById('btn-send');
var btnStop = document.getElementById('btn-stop');
var statusDot = document.getElementById('status-dot');
var statusText = document.getElementById('status-text');
var mode = 'chat';
var advRound = 0;

function connect() {{
    var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(protocol + '//' + location.host + '/ws');
    ws.onopen = function() {{
        console.log('WS connected');
        document.getElementById('key-info').textContent = '已连接';
                setTimeout(function() {{ loadSessions(); }}, 800);
    }};
    ws.onmessage = function(e) {{
        var msg = JSON.parse(e.data);
        handleMessage(msg);
    }};
    ws.onerror = function(e) {{
        console.error('WS error:', e);
    }};
    ws.onclose = function(e) {{
        console.log('WS disconnected (code=' + e.code + '), reconnecting in 2s...');
        setTimeout(connect, 2000);
    }};
}}
connect();

function handleMessage(msg) {{
    console.log('handleMessage: type=' + msg.type + (msg.role ? ' role=' + msg.role : '') + (msg.content ? ' content=' + msg.content.substring(0,80) : ''));

    // Get the actual last .msg-group.ai (querySelector returns FIRST match, not last)
    function getLastAiGroup() {{
        var all = chat.querySelectorAll('.msg-group.ai');
        return all.length > 0 ? all[all.length - 1] : null;
    }}

    // Check if last visible element is a user message; if so, AI response starts fresh
    function shouldStartNewAiGroup() {{
        var last = chat.lastElementChild;
        if (!last) return true;
        // Skip tool-card and system messages, but treat them as a boundary
        var skipped = false;
        while (last && (last.classList.contains('tool-card') || last.classList.contains('system'))) {{
            last = last.previousElementSibling;
            skipped = true;
        }}
        // After agent_dispatch or tool-card, always start a new AI group
        if (skipped) return true;
        if (!last) return true;
        // addMsg wraps messages in a classless div; check inner .msg-group
        var inner = last.classList.contains('msg-group') ? last : last.querySelector('.msg-group');
        if (!inner) return true;
        return inner.classList.contains('user');
    }}

    switch (msg.type) {{
        case 'status':
            if (msg.state === 'running') {{ statusDot.className = 'status-dot running'; statusText.textContent = '运行中'; btnSend.style.display = 'none'; btnStop.style.display = ''; }}
            else {{ statusDot.className = 'status-dot idle'; statusText.textContent = '就绪'; btnSend.style.display = ''; btnStop.style.display = 'none'; }}
            break;
        case 'text_chunk':
            {{
                var htmlContent = escapeHtml(msg.content);
                var fresh = shouldStartNewAiGroup();
                if (fresh) {{
                    var div = document.createElement('div');
                    div.innerHTML = renderMsg(msg.role || 'project_manager', 'ai', htmlContent);
                    chat.appendChild(div);
                }} else {{
                    var lastMsg = getLastAiGroup();
                    if (!lastMsg) {{
                        var div = document.createElement('div');
                        div.innerHTML = renderMsg(msg.role || 'project_manager', 'ai', '');
                        chat.appendChild(div);
                        lastMsg = div.querySelector('.msg-group.ai');
                    }}
                    lastMsg.querySelector('.msg-bubble').innerHTML += htmlContent;
                }}
            }}
            scrollToBottom();
            break;
        case 'tool_call':
            var card = document.createElement('div');
            card.className = 'tool-card';
            card.style.marginLeft = '42px';
            card.innerHTML = '<div class="tc-name">🔧 ' + escapeHtml(msg.name) + '</div><div class="tc-status">执行中...</div>';
            chat.appendChild(card);
            scrollToBottom();
            break;
        case 'tool_result':
            var card = chat.querySelector('.tool-card:last-child');
            if (card) {{
                card.querySelector('.tc-status').textContent = '完成';
                var res = document.createElement('div');
                res.className = 'tc-result';
                res.textContent = msg.content;
                card.appendChild(res);
            }}
            break;
        case 'final_answer':
            if (msg.content) {{
                var fresh = shouldStartNewAiGroup();
                if (fresh) {{
                    var div = document.createElement('div');
                    div.innerHTML = renderMsg(msg.role || 'project_manager', 'ai', formatContent(msg.content));
                    chat.appendChild(div);
                }} else {{
                    var lastAi = getLastAiGroup();
                    if (lastAi) {{
                        lastAi.querySelector('.msg-bubble').innerHTML = formatContent(msg.content);
                    }} else {{
                        addAiMsg(msg.content, msg.role || 'project_manager');
                    }}
                }}
            }}
            scrollToBottom();
            break;
        case 'agent_dispatch':
            var div = document.createElement('div');
            div.className = 'msg-group system';
            div.innerHTML = '<div class="msg-bubble" style="background:transparent;border:none;font-size:11px;color:var(--text-muted);">🔄 正在调用 <span style="color:var(--accent-cyan);">' + escapeHtml(msg.role_display || msg.role) + '</span>...</div>';
            chat.appendChild(div);
            scrollToBottom();
            break;
        case 'agent_response':
            addAiMsg(msg.content, msg.role);
            break;
        case 'error':
            var div = document.createElement('div');
            div.className = 'msg-group system';
            div.innerHTML = '<span style="color:var(--error);">错误: ' + escapeHtml(msg.message) + '</span>';
            chat.appendChild(div);
            scrollToBottom();
            break;
        case 'thinking':
            var tb = document.createElement('div');
            tb.className = 'thinking-block';
            var header = document.createElement('div');
            header.className = 'thinking-header';
            header.innerHTML = '💭 <span class="thinking-toggle">展开</span>';
            header.onclick = function() {{
                var content = this.nextElementSibling;
                var toggle = this.querySelector('.thinking-toggle');
                var isHidden = content.style.display === 'none';
                content.style.display = isHidden ? 'block' : 'none';
                toggle.textContent = isHidden ? '收起' : '展开';
            }};
            tb.appendChild(header);
            var tc = document.createElement('div');
            tc.className = 'thinking-content';
            tc.style.display = 'none';
            tc.textContent = msg.content;
            tb.appendChild(tc);
            // Insert before the last AI group
            var lastAi = getLastAiGroup();
            if (lastAi) {{
                lastAi.parentNode.insertBefore(tb, lastAi);
            }} else {{
                chat.appendChild(tb);
            }}
            scrollToBottom();
            break;
        case 'session_switched':
            currentSessionId = msg.session_id;
            var sidEl = document.getElementById('current-session-id');
            if (sidEl) sidEl.textContent = 'SID:' + (msg.session_id || '');
            if (msg.messages) {{
                chat.innerHTML = '';
                for (var m of msg.messages) {{
                    if (m.type) {{
                        // Rich message: replay through handleMessage
                        handleMessage(m);
                    }} else if (m.role === 'user') {{
                        addMsg('user', m.content);
                    }} else if (m.role === 'system') {{
                        /* skip system prompt */
                    }} else {{
                        // Legacy format: role/content only
                        addMsg('ai', m.content, m.role || 'project_manager');
                    }}
                }}
            }}
            loadSessions();
            setTimeout(function() {{ scrollToBottom(); }}, 100);
            break;
        case 'session_list':
            renderSessions(msg.sessions);
            break;
    }}
}}

function send() {{
    var text = msgInput.value.trim();
    if (!text) return;
    addMsg('user', text);
    msgInput.value = '';
    msgInput.style.height = 'auto';

    // Check for user @mention to route to specific role
    var mentionMatch = text.match(/@(project_manager|product_manager|architect|developer|code_reviewer|bug_hunter|doc_writer)/);
    var targetRole = mentionMatch ? mentionMatch[1] : 'project_manager';
    var content = mentionMatch ? text.replace(mentionMatch[0], '').trim() : text;

    console.log('send(): ws.readyState=' + (ws ? ws.readyState : 'null') + ' role=' + targetRole + ' content=' + content);

    if (!ws) {{
        console.error('send(): ws is null, attempting reconnect');
        connect();
        addMsg('ai', '连接已断开，正在重连，请稍后重试...', 'project_manager');
        return;
    }}

    if (ws.readyState !== WebSocket.OPEN) {{
        console.error('send(): ws not open, readyState=' + ws.readyState);
        addMsg('ai', 'WebSocket 未连接 (状态:' + ws.readyState + ')，请刷新页面后重试', 'project_manager');
        return;
    }}

    ws.send(JSON.stringify({{type: 'develop', content: content || text, role: targetRole}}));
    console.log('send(): message sent OK');
}}

function interrupt() {{
    if (ws && ws.readyState === WebSocket.OPEN) {{
        ws.send(JSON.stringify({{type: 'interrupt'}}));
    }}
}}

function setMode(m) {{
    mode = m;
    document.getElementById('mode-chat').style.color = m === 'chat' ? 'var(--accent-cyan)' : 'var(--text-muted)';
    document.getElementById('mode-review').style.color = m === 'review' ? 'var(--accent-cyan)' : 'var(--text-muted)';
}}

// ---- Chat helpers ----
function addMsg(type, content, role) {{
    var div = document.createElement('div');
    if (type === 'ai') {{
        div.innerHTML = renderMsg(role || 'project_manager', 'ai', formatContent(content));
    }} else {{
        div.innerHTML = renderUserMsg(content);
    }}
    chat.appendChild(div);
    scrollToBottom();
}}

function addAiMsg(content, role) {{
    addMsg('ai', content, role);
}}

marked.setOptions({{
    breaks: true,
    gfm: true
}});
function formatContent(text) {{
    if (!text) return '';
    try {{
        var html = marked.parse(text);
        return linkifyFilePaths(html);
    }} catch(e) {{ return escapeHtml(text); }}
}}

function escapeHtml(text) {{
    var d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}}

function renderMsg(role, className, content) {{
    var roles = {{'project_manager':{{'av':'PJM','nm':'项目经理','cl':'pjm'}},'product_manager':{{'av':'PDM','nm':'产品经理','cl':'pdm'}},'architect':{{'av':'AR','nm':'架构师','cl':'arch'}},'developer':{{'av':'DV','nm':'开发者','cl':'dev'}},'code_reviewer':{{'av':'RV','nm':'审查员','cl':'rev'}},'bug_hunter':{{'av':'BH','nm':'Bug猎人','cl':'hunt'}},'doc_writer':{{'av':'DW','nm':'文档编写者','cl':'doc'}}}};
    var r = roles[role] || {{'av':'AI','nm':role,'cl':'pdm'}};
    var html = '<div class="msg-group ' + className + '">';
    html += '<div class="msg-avatar ' + r.cl + '">' + r.av + '</div>';
    html += '<div class="msg-body">';
    html += '<div class="msg-sender ' + r.cl + '">' + r.nm + '</div>';
    html += '<div class="msg-bubble">' + content + '</div>';
    html += '</div></div>';
    return html;
}}

function renderUserMsg(content) {{
    var html = '<div class="msg-group user">';
    html += '<div class="msg-avatar user">U</div>';
    html += '<div class="msg-body">';
    html += '<div class="msg-sender" style="color:#c084fc;text-align:right;">你</div>';
    html += '<div class="msg-bubble">' + escapeHtml(content) + '</div>';
    html += '</div></div>';
    return html;
}}

function scrollToBottom() {{
    var container = document.getElementById('chat') || document.getElementById('tab-chat');
    if (container) container.scrollTop = container.scrollHeight;
}}

// Floating scroll-to-bottom button
var scrollBtn = null;
document.addEventListener('DOMContentLoaded', function() {{
    scrollBtn = document.createElement('div');
    scrollBtn.style.cssText = 'position:fixed;bottom:100px;right:30px;width:36px;height:36px;border-radius:50%;background:var(--bg-tertiary);border:1px solid var(--border);color:var(--text-secondary);display:flex;align-items:center;justify-content:center;cursor:pointer;z-index:30;font-size:18px;opacity:0;transition:opacity 0.2s;';
    scrollBtn.innerHTML = '↓';
    scrollBtn.title = '回到最新消息';
    scrollBtn.onclick = function() {{ scrollToBottom(); }};
    document.body.appendChild(scrollBtn);
}});

// ---- Scroll detection for floating button ----
var chatContainer = document.getElementById('chat');
if (chatContainer) {{
    chatContainer.addEventListener('scroll', function() {{
        if (!scrollBtn) return;
        var atBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 100;
        scrollBtn.style.opacity = atBottom ? '0' : '1';
    }});
}}

// ---- Input auto-resize ----
msgInput.addEventListener('input', function() {{
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
}});

msgInput.addEventListener('keydown', function(e) {{
    if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); send(); }}
}});

// ---- Session Management ----
function loadSessions() {{
    if (ws && ws.readyState === WebSocket.OPEN) {{
        var currentProject = document.getElementById('project-select').value || 'default';
        ws.send(JSON.stringify({{type: 'session_list', project: currentProject}}));
    }}
}}

async function newSession() {{
    try {{
        var currentProject = document.getElementById('project-select').value || 'default';
        var r = await fetch('/api/sessions', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{project: currentProject, role:roleSelect.value}})}});
        var data = await r.json();
        currentSessionId = data.session_id;
        chat.innerHTML = '';
        if (ws && ws.readyState === WebSocket.OPEN) {{
            ws.send(JSON.stringify({{type:'session_switch', session_id: data.session_id}}));
        }}
    }} catch(e) {{ console.error(e); }}
}}

function renderSessions(sessions) {{
    var el = document.getElementById('session-list');
    el.innerHTML = sessions.map(function(s) {{
        var active = s.id === currentSessionId ? ' active' : '';
        var time = s.updated_at ? s.updated_at.replace('T',' ') : '';
        return '<div class="session-item' + active + '" onclick="switchSession(\\'' + s.id + '\\')">' +
            '<div class="s-title">' + escapeHtml(s.title || '新对话') + '<span class="session-id-badge" title="会话ID，点击复制">' + escapeHtml(s.id) + '</span></div>' +
            '<div class="s-meta">' + (s.message_count||0) + ' 条消息 · ' + escapeHtml(s.role||'') + (time ? ' · ' + time : '') + '</div>' +
            '<div class="s-actions"><a onclick="event.stopPropagation();deleteSession(\\''+s.id+'\\')">删除</a> <a onclick="event.stopPropagation();copySessionId(\\''+s.id+'\\')">复制ID</a></div></div>';
    }}).join('');
}}

function copySessionId(sid) {{
    navigator.clipboard.writeText(sid).then(function() {{
        alert('会话ID已复制: ' + sid);
    }}).catch(function() {{
        prompt('会话ID (手动复制):', sid);
    }});
}}

async function switchSession(sid) {{
    document.getElementById('session-panel').classList.remove('open');
    if (ws && ws.readyState === WebSocket.OPEN) {{
        ws.send(JSON.stringify({{type:'session_switch', session_id: sid}}));
    }}
}}

async function deleteSession(sid) {{
    if (!confirm('删除此会话？')) return;
    try {{
        var currentProject = document.getElementById('project-select').value || 'default';
        await fetch('/api/sessions/' + sid + '?project=' + encodeURIComponent(currentProject), {{method:'DELETE'}});
        if (sid === currentSessionId) {{
            currentSessionId = null;
            chat.innerHTML = '<div class=\"welcome\" id=\"welcome\"><h2>HGJ-dev</h2><p>AI 驱动的开发助手</p></div>';
        }}
        loadSessions();
    }} catch(e) {{ console.error(e); }}
}}

// ---- Project Selector ----
async function loadProjectsDropdown() {{
    try {{
        var r = await fetch('/api/projects');
        var data = await r.json();
        var sel = document.getElementById('project-select');
        sel.innerHTML = '';
        var activeName = (data.active && data.active.name) || '';
        var activePath = (data.active && data.active.path) || '';
        if (!data.projects || !data.projects.length) {{
            sel.innerHTML = '<option value=\"\">-- 未配置项目 --</option>';
            document.getElementById('project-info').textContent = '暂无项目 — 请先添加项目';
            document.getElementById('project-info').style.color = 'var(--warning)';
            return;
        }}
        for (var p of data.projects) {{
            var selected = (p.name === activeName) ? ' selected' : '';
var tag = p.is_external ? ' [外部]' : '';
            sel.innerHTML += '<option value=\"' + escapeHtml(p.name) + '\"' + selected + '>' + escapeHtml(p.name) + tag + '</option>';
        }}
        document.getElementById('project-info').textContent = activePath || getCwdFallback();
        document.getElementById('project-info').style.color = 'var(--accent-cyan)';
        var hint = document.getElementById('no-project-hint');
        if (hint) hint.style.display = 'none';
    }} catch(e) {{}}
    // Show hint if no projects
    var sel = document.getElementById('project-select');
    if (sel.options.length === 0 || sel.value === '' || sel.options[0].value === '') {{
        var hint = document.getElementById('no-project-hint');
        if (hint) hint.style.display = 'block';
        document.getElementById('project-info').style.color = 'var(--warning)';
    }}
}}

function getCwdFallback() {{
    return '~';
}}

async function switchActiveProject() {{
    var name = document.getElementById('project-select').value;
    if (!name) return;
    try {{
        await fetch('/api/projects/' + encodeURIComponent(name) + '/switch', {{method:'POST'}});
        loadProjectsDropdown();
        // Switch WebSocket session project and reload sessions
        currentSessionId = null;
        chat.innerHTML = '<div class=\"welcome\" id=\"welcome\"><h2>HGJ-dev</h2><p>AI 驱动的开发助手</p></div>';
        if (ws && ws.readyState === WebSocket.OPEN) {{
            ws.send(JSON.stringify({{type:'session_list'}}));
        }}
    }} catch(e) {{ console.error(e); }}
}}

// ---- Projects List ----
async function loadProjects() {{
    try {{
        var r = await fetch('/api/projects');
        var data = await r.json();
        var el = document.getElementById('projects-list');
        if (!data.projects || !data.projects.length) {{
            el.innerHTML = '<p style="color:var(--text-muted);font-size:13px;margin-bottom:16px;">暂无项目 — 使用下方表单新建项目或打开已有项目</p>';
            return;
        }}
        var html = '<table class="projects-table"><tr><th>名称</th><th>路径</th><th>GitHub</th><th>类型</th><th>描述</th><th>状态</th><th>操作</th></tr>';
        for (var p of data.projects) {{
            var typeTag = p.is_external ? '<span style=\"color:var(--accent-cyan);font-size:10px;\">📂 外部</span>' : '<span style=\"color:var(--success);font-size:10px;\">🏠 工作区</span>';
            var desc = p.description || '<span style=\"color:var(--text-muted);font-size:10px;\">无描述</span>';
            var github = p.github_url ? '<a href=\"' + escapeHtml(p.github_url) + '\" target=\"_blank\" style=\"color:var(--accent-cyan);font-size:10px;font-family:var(--font-mono);\">🔗</a>' : '<span style=\"color:var(--text-muted);font-size:10px;\">—</span>';
            var activeBadge = p.active ? ' style=\"background:var(--bg-tertiary)\"' : '';
            var switchBtn = p.active ? '<span style=\"color:var(--success);font-size:11px;\">✓ 当前</span>' : '<button class=\"btn btn-secondary\" style=\"padding:3px 8px;font-size:11px;background:var(--accent-cyan);color:#000;border:none;\" onclick=\"switchProject(\\''+escapeHtml(p.name)+'\\')\">切换</button>';
            html += '<tr' + activeBadge + '>';
            html += '<td style=\"font-weight:600;\">' + escapeHtml(p.name) + '</td>';
            html += '<td style=\"font-size:11px;font-family:var(--font-mono);\">' + escapeHtml(p.path) + '</td>';
            html += '<td style=\"text-align:center;\">' + github + '</td>';
            html += '<td>' + typeTag + '</td>';
            html += '<td style=\"font-size:11px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;\">' + desc + '</td>';
            html += '<td>' + (p.active ? '当前' : '') + '</td>';
            html += '<td style=\"white-space:nowrap;\">' + switchBtn + ' <button class=\"btn btn-secondary\" style=\"padding:3px 8px;font-size:11px;background:var(--error);color:white;border:none;\" onclick=\"removeProject(\\''+escapeHtml(p.name)+'\\')\">删除</button></td></tr>';
        }}
        html += '</table>';
        el.innerHTML = html;
    }} catch(e) {{
        document.getElementById('projects-list').innerHTML = '<p style=\"color:var(--error);\">加载失败: ' + e.message + '</p>';
    }}
}}

async function addProject() {{
    var name = document.getElementById('pname').value.trim();
    var desc = document.getElementById('pdesc').value.trim();
    var github = document.getElementById('pgithub').value.trim();
    if (!name) {{ alert('请输入项目名称'); return; }}
    var body = {{name: name, description: desc, github_url: github}};
    await fetch('/api/projects', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(body)}});
    document.getElementById('pname').value = '';
    document.getElementById('pdesc').value = '';
    document.getElementById('pgithub').value = '';
    loadProjects();
    loadProjectsDropdown();
}}

async function addExternalProject() {{
    var name = document.getElementById('epname').value.trim();
    var path = document.getElementById('eppath').value.trim();
    var desc = document.getElementById('epdesc').value.trim();
    var github = document.getElementById('epgithub').value.trim();
    if (!name || !path) {{ alert('请输入项目名称和路径'); return; }}
    var body = {{name: name, path: path, description: desc, is_external: true, github_url: github}};
    await fetch('/api/projects', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(body)}});
    document.getElementById('epname').value = '';
    document.getElementById('eppath').value = '';
    document.getElementById('epdesc').value = '';
    document.getElementById('epgithub').value = '';
    loadProjects();
    loadProjectsDropdown();
}}

async function switchProject(name) {{
    await fetch('/api/projects/' + encodeURIComponent(name) + '/switch', {{method:'POST'}});
    loadProjects();
    loadProjectsDropdown();
}}

async function removeProject(name) {{
    await fetch('/api/projects/' + encodeURIComponent(name), {{method:'DELETE'}});
    loadProjects();
    loadProjectsDropdown();
}}

// ---- File Browser ----
async function listDir(path) {{
    try {{
        var r = await fetch('/api/files?path=' + encodeURIComponent(path));
        var data = await r.json();
        var el = document.getElementById('file-listing');
        var html = '';
        if (data.parent) html += '<div style="margin-bottom:8px;font-size:12px;"><a style="color:var(--accent-cyan);cursor:pointer;" onclick="listDir(\\'' + escapeHtml(data.parent) + '\\')">📁 ..</a></div>';
        html += '<table class="files-table"><tr><th>名称</th><th>大小</th><th>修改时间</th></tr>';
        for (var item of (data.entries || [])) {{
            var size = item.size > 1024 ? (item.size/1024).toFixed(1) + 'KB' : item.size + 'B';
            var escapedPath = escapeHtml(item.path).replace(/\\\\/g, '/');
            var escapedName = escapeHtml(item.name);
            if (item.is_dir) {{
                html += '<tr><td><a style=\"color:var(--accent-cyan);cursor:pointer;text-decoration:none;\" onclick=\"listDir(\\'' + escapedPath + '\\')\">📁 ' + escapedName + '</a></td>';
            }} else {{
                html += '<tr><td><a style=\"color:var(--text-primary);cursor:pointer;text-decoration:none;\" onclick=\"viewFile(\\'' + escapedPath + '\\')\">📄 ' + escapedName + '</a></td>';
            }}
            html += '<td>' + size + '</td>';
            html += '<td>' + new Date(item.modified*1000).toLocaleString() + '</td></tr>';
        }}
        html += '</table>';
        el.innerHTML = html;
    }} catch(e) {{}}
}}

async function viewFile(path) {{
    // Use the full-featured file viewer modal (supports markdown, syntax highlighting)
    openFileViewer(path);
}}

// ---- Settings ----
var modelLists = {{
    anthropic: [['claude-opus-4-6','Claude Opus 4.6'],['claude-sonnet-4-6','Claude Sonnet 4.6'],['claude-haiku-4-5-20251001','Claude Haiku 4.5']],
    openai: [['gpt-4o','GPT-4o'],['gpt-4o-mini','GPT-4o mini'],['gpt-4-turbo','GPT-4 Turbo']],
    openrouter: [['anthropic/claude-sonnet-4-6','Claude Sonnet 4.6'],['openai/gpt-4o','GPT-4o']],
    deepseek: [['deepseek-v4-flash','DeepSeek V4 Flash'],['deepseek-v4-pro','DeepSeek V4 Pro'],['deepseek-chat','DeepSeek Chat'],['deepseek-reasoner','DeepSeek Reasoner']],
    qwen: [['qwen-max','Qwen Max'],['qwen-plus','Qwen Plus'],['qwen-turbo','Qwen Turbo']],
    zhipu: [['glm-4-plus','GLM-4 Plus'],['glm-4-flash','GLM-4 Flash']],
    moonshot: [['moonshot-v1-32k','Moonshot 32K'],['moonshot-v1-128k','Moonshot 128K']],
    siliconflow: [['Qwen/Qwen2.5-72B-Instruct','Qwen2.5-72B'],['deepseek-ai/DeepSeek-V3','DeepSeek V3']],
    custom: [['custom','Custom']],
}};

var defaultUrls = {{
    deepseek: 'https://api.deepseek.com', qwen: 'https://dashscope.aliyuncs.com',
    zhipu: 'https://open.bigmodel.cn/api/paas/v4', moonshot: 'https://api.moonshot.cn',
    siliconflow: 'https://api.siliconflow.cn', custom: '',
}};

function updateModels(provider) {{
    var sel = document.getElementById('s-model');
    sel.innerHTML = '';
    var list = modelLists[provider] || modelLists.custom;
    for (var m of list) {{
        var opt = document.createElement('option');
        opt.value = m[0]; opt.textContent = m[1];
        sel.appendChild(opt);
    }}
    var urlInput = document.getElementById('s-base-url');
    if (defaultUrls[provider]) urlInput.value = defaultUrls[provider];
}}

function applySettings(settings) {{
    document.getElementById('s-provider').value = settings.provider || 'deepseek';
    updateModels(settings.provider || 'deepseek');
    document.getElementById('s-model').value = settings.model || 'deepseek-v4-flash';
    document.getElementById('s-model-custom').value = settings.model_custom || '';
    document.getElementById('s-base-url').value = settings.base_url || (defaultUrls[settings.provider] || '');
    document.getElementById('s-api-key').value = settings.api_key || '';
    document.getElementById('s-user-title').value = settings.user_title || '用户';
}}

document.getElementById('s-provider').addEventListener('change', function() {{
    updateModels(this.value);
}});

if (typeof SETTINGS !== 'undefined') applySettings(SETTINGS);

async function saveSettings() {{
    var body = {{
        provider: document.getElementById('s-provider').value,
        model: document.getElementById('s-model').value,
        model_custom: document.getElementById('s-model-custom').value.trim(),
        api_key: document.getElementById('s-api-key').value.trim(),
        base_url: document.getElementById('s-base-url').value.trim(),
        user_title: document.getElementById('s-user-title').value.trim(),
    }};
    try {{
        var r = await fetch('/api/settings', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(body)}});
        var data = await r.json();
        if (data.error) {{ alert('错误: ' + data.error); }}
        else {{ alert('设置已保存!'); }}
    }} catch(e) {{ alert('保存失败: ' + e.message); }}
}}

async function clearSettings() {{
    if (!confirm('清除所有设置？')) return;
    try {{
        await fetch('/api/settings', {{method:'DELETE'}});
        applySettings({{provider:'deepseek', model:'deepseek-v4-flash', model_custom:'', api_key:'', base_url:''}});
        alert('已清除');
    }} catch(e) {{}}
}}

async function testConnection() {{
    try {{
        var r = await fetch('/api/settings/test', {{method:'POST'}});
        var data = await r.json();
        if (data.ok) {{ alert('连接成功! 模型: ' + data.model); }}
        else {{ alert('连接失败: ' + data.error); }}
    }} catch(e) {{ alert('测试失败: ' + e.message); }}
}}

document.addEventListener('DOMContentLoaded', function() {{
    loadProjectsDropdown();
    if (ACTIVE_TAB === 'projects') loadProjects();
    if (ACTIVE_TAB === 'files') listDir('');
    // Check API key status
    checkApiKeyStatus();
}});

async function checkApiKeyStatus() {{
    try {{
        var r = await fetch('/api/status');
        var data = await r.json();
        var hint = document.getElementById('no-api-key-hint');
        if (hint) {{
            hint.style.display = data.has_api_key ? 'none' : 'block';
        }}
    }} catch(e) {{}}
}}

// ---- File Viewer Modal ----
var fileModalOverlay = null;
var fileModalBody = null;
var fileRawContent = '';
var fileMdView = false;

function ensureFileModal() {{
    if (fileModalOverlay) return;
    fileModalOverlay = document.createElement('div');
    fileModalOverlay.className = 'file-modal-overlay';
    fileModalOverlay.onclick = function(e) {{ if (e.target === fileModalOverlay) closeFileViewer(); }};
    fileModalOverlay.innerHTML = '<div class="file-modal">' +
        '<div class="file-modal-header">' +
            '<span class="fm-path" id="fm-path"></span>' +
            '<span style="flex:1"></span>' +
            '<button class="btn btn-secondary" id="fm-md-toggle" style="display:none;padding:4px 10px;font-size:11px;margin-right:8px;" onclick="event.stopPropagation();toggleMdView()">Markdown 预览</button>' +
            '<button class="fm-close" onclick="closeFileViewer()">&times;</button>' +
        '</div>' +
        '<div class="file-modal-body loading" id="fm-body">加载中...</div>' +
        '<div class="file-modal-footer">' +
            '<span id="fm-info"></span>' +
            '<span>Esc 关闭</span>' +
        '</div>' +
    '</div>';
    document.body.appendChild(fileModalOverlay);
    fileModalBody = document.getElementById('fm-body');
}}

async function openFileViewer(filepath) {{
    ensureFileModal();
    document.getElementById('fm-path').textContent = filepath;
    fileModalBody.className = 'file-modal-body loading';
    fileModalBody.textContent = '加载中...';
    fileRawContent = '';
    fileMdView = false;
    fileModalOverlay.classList.add('open');
    try {{
        var resolvedPath = filepath;
        var r = await fetch('/api/files/content?path=' + encodeURIComponent(filepath));
        // Fallback: if file not found and path has no directory, search project
        if (r.status === 404 && filepath.indexOf('/') === -1 && filepath.indexOf('\\\\') === -1) {{
            var searchR = await fetch('/api/files/search?path=.&pattern=' + encodeURIComponent(filepath));
            var searchData = await searchR.json();
            if (searchData.matches && searchData.matches.length > 0) {{
                // Pick the best match (prefer exact filename match, shortest path)
                var best = null;
                for (var m of searchData.matches) {{
                    if (m.endsWith('/' + filepath) || m === filepath) {{
                        if (!best || m.length < best.length) best = m;
                    }}
                }}
                if (!best) best = searchData.matches[0];
                resolvedPath = best;
                r = await fetch('/api/files/content?path=' + encodeURIComponent(resolvedPath));
            }}
        }}
        var data = await r.json();
        var ext = resolvedPath.replace(/^.*[.]/, '').toLowerCase();
        var toggleBtn = document.getElementById('fm-md-toggle');
        document.getElementById('fm-path').textContent = resolvedPath;
        if (data.is_binary) {{
            fileModalBody.className = 'file-modal-body error';
            fileModalBody.textContent = '[二进制文件，无法预览]';
            document.getElementById('fm-info').textContent = '';
            toggleBtn.style.display = 'none';
        }} else if (!data.content && data.detail) {{
            fileModalBody.className = 'file-modal-body error';
            fileModalBody.textContent = '文件未找到: ' + filepath + (resolvedPath !== filepath ? '\\n已搜索项目目录，未找到匹配文件' : '');
            document.getElementById('fm-info').textContent = '';
            toggleBtn.style.display = 'none';
        }} else {{
            fileRawContent = data.content || '';
            fileModalBody.className = 'file-modal-body';
            fileModalBody.textContent = fileRawContent || '(空文件)';
            var lines = (fileRawContent || '').split('\\n').length;
            var truncated = data.truncated ? ' (仅显示前500行)' : '';
            document.getElementById('fm-info').textContent = lines + ' 行' + truncated;
            if (ext === 'md' || ext === 'mdx' || ext === 'markdown') {{
                toggleBtn.style.display = '';
                toggleBtn.textContent = 'Markdown 预览';
            }} else {{
                toggleBtn.style.display = 'none';
            }}
        }}
    }} catch(e) {{
        fileModalBody.className = 'file-modal-body error';
        fileModalBody.textContent = '加载失败: ' + e.message;
        document.getElementById('fm-info').textContent = '';
        document.getElementById('fm-md-toggle').style.display = 'none';
    }}
}}

function toggleMdView() {{
    var toggleBtn = document.getElementById('fm-md-toggle');
    if (!fileRawContent) return;
    fileMdView = !fileMdView;
    if (fileMdView) {{
        toggleBtn.textContent = '原始文本';
        fileModalBody.className = 'file-modal-body md-rendered';
        try {{
            fileModalBody.innerHTML = marked.parse(fileRawContent);
        }} catch(e) {{
            fileModalBody.textContent = fileRawContent;
        }}
    }} else {{
        toggleBtn.textContent = 'Markdown 预览';
        fileModalBody.className = 'file-modal-body';
        fileModalBody.textContent = fileRawContent;
    }}
}}

function closeFileViewer() {{
    if (fileModalOverlay) fileModalOverlay.classList.remove('open');
    fileRawContent = '';
    fileMdView = false;
}}

document.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape') closeFileViewer();
}});

// ---- File path linkifier ----
function linkifyFilePaths(html) {{
    // Normalize Windows backslash paths to forward slashes
    html = html.replace(/\\\\/g, '/');

    var codeExtList = ['py','md','json','js','ts','jsx','tsx','html','css','scss','less','yaml','yml','toml','cfg','ini','txt','rs','go','java','c','cpp','h','hpp','sh','bash','bat','ps1','xml','svg','sql','sqlite','env','lock','gitignore','dockerignore','editorconfig','Makefile','Dockerfile','log','conf','cnf','cfg','ini','prop','properties','gradle','sbt','csproj','vbproj','fsproj','sln','cs','vb','fs','r','rmd','R','Rmd','jl','kt','kts','swift','scala','clj','cljs','edn','ex','exs','erl','hrl','hs','lhs','rb','rake','gemspec','php','phtml','twig','pl','pm','t','lua','vim','zsh','fish','tf','tfvars','proto','thrift','graphql','gql','prisma','vue','svelte','astro','mdx','mjml','njk','hbs','ejs','pug','jade','styl','sass','pcss','postcss','wxss','acss','nss','qss'];
    var codeExt = '(?:' + codeExtList.join('|') + ')';
    var re = new RegExp('(?:^|[^a-zA-Z0-9_/.-])((?:~?/|[.]{{0,2}}/|[a-zA-Z]:/|[a-zA-Z0-9_.][a-zA-Z0-9_./-]*/)[a-zA-Z0-9_./:-]*[a-zA-Z0-9_-][.]' + codeExt + '|[a-zA-Z0-9_][a-zA-Z0-9_.-]{{1,40}}[.]' + codeExt + '|[Dd]ockerfile|[Mm]akefile|[Dd]ocker-compose[.]ya?ml)(?=[^a-zA-Z0-9_./-]|$)', 'gi');
    return html.replace(re, function(match) {{
        var path = match.replace(/^[^a-zA-Z0-9_/~.]+/, '');
        if (/^https?:/i.test(path)) return match;
        var esc = path.replace(/"/g, '&quot;');
        return match.replace(path, '<a class="file-link" data-filepath="' + esc + '" href="javascript:void(0)" onclick="event.stopPropagation();openFileViewer(this.getAttribute(\\'data-filepath\\'));" title="点击查看: ' + esc + '">' + path + '</a>');
    }});
}}

</script>
</body>
</html>"""


# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(title="HGJ-dev Dashboard", version="0.1.0-dev")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from harnessgenj_dev.web.session_manager import SessionManager
    from harnessgenj_dev.tools.registry import auto_register

    auto_register()
    app.state.session_manager = SessionManager()
    # Initialize knowledge files for roles with active project
    try:
        from harnessgenj_dev.projects import get_active_project
        active = get_active_project()
        if active and active.get("path"):
            from harnessgenj_dev.memory.role_registry import list_roles, init_role_memory
            for r in list_roles():
                if r.get("knowledge_file"):
                    init_role_memory(r["id"], project_path=active["path"])
    except Exception:
        pass
    yield


app.router.lifespan_context = lifespan


# ============================================================
# Agent Session
# ============================================================

_DEFAULT_TEAM_ROLE = "project_manager"

_KF_MAINTENANCE_PATTERNS = [
    "更新知识库", "写入知识库", "保存知识库", "记录到知识库",
    "更新 .project-knowledge", "写入 .project-knowledge",
    "记录到 .project-knowledge", "知识库已更新", "知识库更新",
    "update .project-knowledge", "write .project-knowledge",
    "save .project-knowledge", "update knowledge", "save knowledge",
    "updating knowledge", "saving knowledge", "knowledge updated",
]


def _is_kf_maintenance(text: str) -> bool:
    """Suppress knowledge-file maintenance chatter from user-facing output."""
    txt = text.lower()
    if ".project-knowledge" not in txt:
        return False
    for pat in _KF_MAINTENANCE_PATTERNS:
        if pat.lower() in txt:
            return True
    return False


class _ConfigShim:
    """Provides project context to agents. Uses active project path or CWD."""

    @property
    def project_path(self) -> str:
        try:
            from harnessgenj_dev.projects import get_active_project

            active = get_active_project()
            if active:
                return active["path"]
        except Exception:
            pass
        return os.getcwd()


class AgentSession:
    def __init__(self, websocket: WebSocket, project: str = "") -> None:
        if not project:
            from harnessgenj_dev.projects import get_active_project

            active = get_active_project()
            project = active["name"] if active else "default"
        self.ws = websocket
        self.role = _DEFAULT_TEAM_ROLE
        self.project = project
        self._agent = None
        self._interrupted = False
        self._running = False
        self._session_id = None
        self._session_mgr = None
        self._develop_task = None
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost_usd = 0.0
        # Per-role sub-agent sessions for work continuity (Claude Code Agent Teams pattern)
        self._sub_sessions: dict[str, str] = {}

    def _get_sub_session(self, role: str):
        """Get or create persistent session for a sub-agent role."""
        mgr = self._get_session_mgr()
        if role not in self._sub_sessions:
            sub = mgr.create_session(self.project + "/sub/" + role, role=role)
            self._sub_sessions[role] = sub.id
        return mgr.get_session(self.project + "/sub/" + role, self._sub_sessions[role])

    @staticmethod
    def _repair_conversation(history: list[dict]) -> list[dict]:
        """Remove orphaned tool messages that lack a preceding assistant with matching tool_calls."""
        repaired = []
        for m in history:
            if m.get("role") == "tool":
                tid = m.get("tool_call_id", "")
                has_parent = False
                # Search backwards for assistant with matching tool_call id
                for p in reversed(repaired):
                    if p.get("role") == "assistant":
                        for tc in p.get("tool_calls", []):
                            if tc.get("id") == tid:
                                has_parent = True
                                break
                        if has_parent:
                            break
                if not has_parent:
                    logger.warning("_repair_conversation: dropping orphan tool msg id=%.20s", tid)
                    continue
            repaired.append(m)
        return repaired

    @staticmethod
    def _compact_sub_session(history: list[dict], max_keep: int = 12) -> list[dict]:
        """Claude Code 3-tier compaction for per-agent independent memory.

        Tier 0 (Repair):   Remove orphaned tool messages without matching assistant tool_calls.
        Tier 1 (Micro-compact): Truncate tool results older than last 5, keep structure.
        Tier 2 (Collapse):   Merge consecutive assistant-only messages.
        Tier 3 (Summarize):  When > max_keep, keep system + last exchange + decision markers.
        """
        history = AgentSession._repair_conversation(history)
        if len(history) <= max_keep:
            return list(history)

        # Tier 1: Truncate old tool results (keep last 5)
        tool_indices = [i for i, m in enumerate(history) if m.get("role") == "tool"]
        if len(tool_indices) > 5:
            for idx in tool_indices[:-5]:
                history[idx] = {
                    "role": "tool",
                    "content": f"[tool result cleared: {len(history[idx].get('content', ''))} chars]",
                    "tool_call_id": history[idx].get("tool_call_id", ""),
                }

        # Tier 2: Collapse — merge consecutive assistant msgs (preserve tool_calls)
        collapsed = []
        i = 0
        while i < len(history):
            m = history[i]
            if m.get("role") == "assistant" and i + 1 < len(history) and history[i + 1].get("role") == "assistant":
                merged_content = m.get("content", "")
                merged_tool_calls = m.get("tool_calls", [])
                j = i + 1
                while j < len(history) and history[j].get("role") == "assistant":
                    merged_content += "\n" + history[j].get("content", "")
                    if not merged_tool_calls:
                        merged_tool_calls = history[j].get("tool_calls", [])
                    j += 1
                collapsed.append({"role": "assistant", "content": merged_content[:3000], "tool_calls": merged_tool_calls})
                i = j
            else:
                collapsed.append(m)
                i += 1

        # Tier 3: If still over max_keep, keep system + last exchange + their context
        if len(collapsed) > max_keep:
            system_msgs = [m for m in collapsed if m.get("role") == "system"]
            decision_markers = [m for m in collapsed if m.get("role") == "assistant"
                              and any(kw in m.get("content", "")[:200] for kw in ("##", "✅", "❌", "完成", "结论"))]
            # Keep last exchange + the assistant message with tool_calls before any tool messages
            recent = collapsed[-6:]
            # Ensure we have the preceding assistant for any tool message in recent
            for idx in range(len(collapsed) - 1, -1, -1):
                if collapsed[idx].get("role") == "tool":
                    # Walk backwards to find prior assistant with tool_calls
                    for jdx in range(idx - 1, max(0, idx - 100), -1):
                        if collapsed[jdx].get("role") == "assistant" and collapsed[jdx].get("tool_calls"):
                            if collapsed[jdx] not in recent:
                                recent.insert(0, collapsed[jdx])
                            break
            seen = set()
            result = []
            for m in system_msgs + decision_markers[-3:] + recent:
                key = (m.get("role"), m.get("content", "")[:100], str(m.get("tool_calls", ""))[:50])
                if key not in seen:
                    result.append(m)
                    seen.add(key)
            return result

        return collapsed

    @property
    def conversation_history(self) -> list[dict[str, str]]:
        session = self._get_session()
        return session.messages if session else []

    @conversation_history.setter
    def conversation_history(self, value: list[dict[str, str]]) -> None:
        session = self._get_session()
        if session:
            session.messages = value

    def _get_session_mgr(self):
        if self._session_mgr is None:
            self._session_mgr = app.state.session_manager
        return self._session_mgr

    def _get_session(self):
        mgr = self._get_session_mgr()
        return mgr.get_session(self.project, self._session_id)

    def _ensure_agent(self):
        if self._agent is None:
            from harnessgenj_dev.core.agent import Agent
            from harnessgenj_dev.llm.gateway import LLMGateway

            gateway = LLMGateway(
                provider=_get_provider(),
                model=_get_model(),
                api_key=_get_api_key(),
                base_url=_get_base_url() or None,
            )
            self._agent = Agent(llm_gateway=gateway, config=_ConfigShim())
        return self._agent

    def _inject_role_memory(self, agent, role: str) -> None:
        pass

    async def _ensure_project(self) -> None:
        """Auto-create a workspace project if none is active (first-use onboarding)."""
        try:
            from harnessgenj_dev.projects import get_active_project, add_project, switch_project

            active = get_active_project()
            if not active:
                proj = add_project("MyProject", description="默认项目 — 由 HarnessGenJ-dev 自动创建")
                switch_project("MyProject")
                self.project = "MyProject"
                logger.info("Auto-created default project: MyProject")
        except Exception:
            pass

    def _build_system_prompt(self, role: str) -> str:
        return self._ensure_agent()._build_system_prompt(role)

    async def ensure_session(self) -> str:
        mgr = self._get_session_mgr()
        session = mgr.get_active_session(self.project)
        if not session:
            session = mgr.create_session(self.project, role=self.role)
        self._session_id = session.id
        if not session.messages:
            system_prompt = self._build_system_prompt(self.role)
            session.messages = [{"role": "system", "content": system_prompt}]
            mgr.save(session)
        return session.id

    def new_session(self, role: str = "developer") -> str:
        mgr = self._get_session_mgr()
        session = mgr.create_session(self.project, role=role)
        self._session_id = session.id
        self.role = role
        self._agent = None
        return session.id

    def switch_session(self, session_id: str) -> bool:
        mgr = self._get_session_mgr()
        session = mgr.get_session(self.project, session_id)
        if not session:
            return False
        mgr._set_active(self.project, session_id)
        self._session_id = session_id
        self.role = session.role or _DEFAULT_TEAM_ROLE
        self._agent = None
        return True

    def delete_session(self, session_id: str) -> bool:
        mgr = self._get_session_mgr()
        result = mgr.delete_session(self.project, session_id)
        if result and self._session_id == session_id:
            self._session_id = None
            self._agent = None
            self._agent = None
        return result

    def save_session(self) -> None:
        session = self._get_session()
        if session:
            session.project = self.project
            self._get_session_mgr().save(session)

    def _append_and_save(self, role: str, content: str, msg_type: str = "agent_response", role_display: str = "") -> None:
        """Append a rich message to session history and persist immediately.

        Claude Code pattern: append-only durable state. Every message is saved
        the moment it's produced, so crashes/restarts never lose data.
        """
        session = self._get_session()
        if not session:
            return
        display = role_display or self._ROLE_DISPLAY.get(role, role)
        session.messages.append({
            "type": msg_type,
            "role": role,
            "role_display": display,
            "content": content,
        })
        session.project = self.project
        self._get_session_mgr().save(session)

    def interrupt(self) -> None:
        self._interrupted = True
        if self._develop_task:
            self._develop_task.cancel()

    async def _send_thinking_if_any(self, agent_or_history, role: str = "") -> None:
        """Send reasoning_content from agent conversation_history as separate 'thinking' message."""
        history = agent_or_history.state.conversation_history if hasattr(agent_or_history, 'state') else agent_or_history
        for msg in reversed(history):
            rc = msg.get("reasoning_content")
            if rc and rc.strip():
                await self.send({
                    "type": "thinking",
                    "role": role or msg.get("role", ""),
                    "content": rc.strip()[:3000],
                })
                break

    async def send(self, data: dict) -> None:
        try:
            await self.ws.send_json(data)
        except Exception:
            pass

    async def _send_status(self, state: str) -> None:
        await self.send({"type": "status", "state": state})

    async def _run_sub_agent(self, role: str, context: str, parent_role: str = "project_manager") -> str:
        """Run a sub-agent with structured output (GitHub handoff contract pattern).

        Agent output format:
        ## 目标: [what this agent aims to achieve]
        ## 约束: [constraints/assumptions]
        ## 发现: [findings/analysis]
        ## 完成标准: [self-check: is the output complete?]
        ## 投票: PASS 或 FAIL:理由
        """
        from harnessgenj_dev.core.agent import Agent
        from harnessgenj_dev.llm.gateway import LLMGateway

        role_display = self._ROLE_DISPLAY.get(role, role)
        await self.send({"type": "agent_dispatch", "role": role, "role_display": role_display, "status": "started"})
        try:
            sub = Agent(
                llm_gateway=LLMGateway(
                    provider=_get_provider(),
                    model=_get_model(),
                    api_key=_get_api_key(),
                    base_url=_get_base_url() or None,
                ),
                config=_ConfigShim(),
                effort="high",
            )
            sub.state.max_iterations = 200
            prompt = (
                "项目经理请你以 "
                + role_display
                + " 身份参与团队分析。请按以下格式输出（用中文）：\n\n"
                + "## 目标\n[你要达成的具体目标]\n\n"
                + "## 约束\n[你的假设和边界条件]\n\n"
                + "## 发现\n[你的分析和发现]\n\n"
                + "## 完成标准\n[你确认你的输出是否完整？是否满足项目要求？]\n\n"
                + "## 投票\n[**PASS** 或 **FAIL:理由**]\n"
                + "- 如果你对前序角色的输出不满意，投FAIL并说明谁需要改进什么\n"
                + "- 如果你满意所有前序工作，投PASS\n\n"
                + "=== 上下文 ===\n"
                + context[:3000]
                + "\n\n"
                + "注意：你只能做你角色范围内的事。不要越权。不能调用其他Agent。"
            )
            # Stream with buffered output for clean display
            acc = ""
            buf = ""
            async for chunk in sub.run_stream(prompt, role=role):
                acc += chunk
                buf += chunk
                if chunk.strip() and ("\n" in chunk or len(buf) > 40):
                    clean = chunk.strip()
                    if clean and not clean.startswith("[Executing") and not clean.startswith("```tool"):
                        await self.send({"type": "text_chunk", "role": role, "content": chunk})
                    buf = ""
            await self._send_thinking_if_any(sub, role)
            await self.send(
                {"type": "final_answer", "role": role, "content": acc.strip() or "(无输出)"}
            )
            return acc.strip() or ""
        except Exception as exc:
            await self.send(
                {"type": "agent_response", "role": role, "role_display": role_display, "content": "错误: " + str(exc)}
            )
            return ""

    async def _run_sub_agent(self, role: str, context: str, silent: bool = False) -> str:
        """Run a sub-agent with given role and context. Returns response text."""
        from harnessgenj_dev.core.agent import Agent
        from harnessgenj_dev.llm.gateway import LLMGateway

        if not silent:
            await self.send(
                {
                    "type": "agent_dispatch",
                    "role": role,
                    "role_display": self._ROLE_DISPLAY.get(role, role),
                    "status": "started",
                }
            )
        try:
            sub = Agent(
                llm_gateway=LLMGateway(
                    provider=_get_provider(),
                    model=_get_model(),
                    api_key=_get_api_key(),
                    base_url=_get_base_url() or None,
                ),
                config=_ConfigShim(),
                effort="high",
            )
            sub.state.max_iterations = 50
            # Load per-agent session, keep only essential context
            sub_session = self._get_sub_session(role)
            if sub_session and sub_session.messages:
                # Repair: remove any orphaned tool messages before loading
                sub_session.messages = self._repair_conversation(sub_session.messages)
                essential = [m for m in sub_session.messages if m.get("role") == "system"]
                if len(sub_session.messages) >= 2:
                    essential += sub_session.messages[-2:]
                sub.state.conversation_history = essential

                # Inject knowledge file with initialization rules
                _kf_context = ""
                try:
                    from ..memory.role_registry import get_role
                    _rc = get_role(role)
                    if _rc and _rc.get("knowledge_file"):
                        _kf_path = _rc["knowledge_file"]
                        _kf_context = (
                            "## 知识库与初始化规则\n"
                            "1. 先 read_file(" + _kf_path + ") 检查知识库是否已初始化\n"
                            "2. 如果内容为空（仅为模板占位符），说明是首次使用："
                            "用 list_directory 看项目结构，read_file 读 PROJECT.md，"
                            "将项目信息写入 " + _kf_path + "，然后开始执行任务\n"
                            "3. 如果已有内容，直接基于上下文开始工作\n"
                            "4. **【强制】任务完成后必须 write_file 更新 " + _kf_path + "**，记录本轮工作、文件变更、关键决策\n"
                            "5. 开始工作前，先 read_file(.project-knowledge/project_status.md) 对齐项目整体进度\n\n"
                        )
                except Exception:
                    pass

            # Inject full role instructions (L2 progressive disclosure)
            from ..memory.role_registry import build_role_instructions
            _role_instructions = build_role_instructions(role)
            task = (
                _role_instructions + "\n\n"
                "你是" + self._ROLE_DISPLAY.get(role, role) + "。EXECUTE the task.\n"
                "CRITICAL: You have file/code tools. CALL them to do the work.\n"
                "Do NOT just describe — actually use the tools.\n\n"
                + _kf_context + context[:2000]
            )
            # Stream output immediately — same behavior as PM, no buffering
            acc = ""
            async for chunk in sub.run_stream(task, role=role):
                acc += chunk
                if not silent and chunk.strip():
                    clean = chunk.strip()
                    if clean and not clean.startswith("[Executing") and not clean.startswith("```tool"):
                        if not _is_kf_maintenance(clean):
                            await self.send({"type": "text_chunk", "role": role, "content": chunk})
            # Claude Code 3-tier compaction for per-agent memory
            if sub_session:
                sub_session.messages = self._compact_sub_session(list(sub.state.conversation_history))
                self._get_session_mgr().save(sub_session)
            if not silent:
                await self.send(
                    {
                        "type": "final_answer",
                        "role": role,
                        "content": acc.strip() or "(无输出)",
                    }
                )
            return acc.strip() or ""
        except Exception as exc:
            if not silent:
                await self.send(
                    {
                        "type": "agent_response",
                        "role": role,
                        "role_display": self._ROLE_DISPLAY.get(role, role),
                        "content": "错误：" + str(exc),
                    }
                )
            return ""

    async def run_develop(self, content: str) -> str | None:
        logger.info("run_develop START: role=%s content=%.50s", self.role, content)
        # Auto-create project if none active (first-use experience)
        await self._ensure_project()
        # Persist user message BEFORE any processing (quick_exec or LLM)
        session = self._get_session()
        if not session.messages:
            system_prompt = self._build_system_prompt(self.role)
            session.messages = [{"role": "system", "content": system_prompt}]
        session.messages.append({"role": "user", "content": content})
        self.save_session()

        agent = self._ensure_agent()
        # Build fresh system prompt so user_title is always current
        fresh_system = self._build_system_prompt(self.role)
        _OPENAI_ROLES = {"system", "user", "assistant", "tool"}
        agent.state.conversation_history = [
            {"role": "system", "content": fresh_system}
            if m.get("role") == "system"
            else {**m, "role": m["role"] if m["role"] in _OPENAI_ROLES else "assistant"}
            for m in session.messages
        ]
        await self._send_status("running")
        accumulated = ""
        try:
            # Stream PM output so user sees real-time progress
            if self.role == "project_manager":
                # Cap at 15 iterations to prevent excessive pre-dispatch file reading.
                # PM should: read project_status.md (1-2) + search_code (1) + read one ref (1) = 3-5 calls,
                # then generate response. 15 is generous even for complex status reports.
                agent.state.max_iterations = 15
            else:
                agent.state.max_iterations = min(agent.state.max_iterations, 3)
            accumulated = ""
            try:
                async for chunk in agent.run_stream(content, role=self.role):
                    accumulated += chunk
                    if chunk.strip():
                        await self.send({"type": "text_chunk", "content": chunk, "role": self.role})
            except Exception as exc:
                logger.exception("PM run_stream failed: %s", exc)
                if not accumulated:
                    accumulated = "分析出错: " + str(exc)[:200]
            await self._send_thinking_if_any(agent, self.role)
            accumulated = accumulated.strip()
            # Anti-monologue: if PM wrote >200 chars without any @mention, rewrite
            if self.role == "project_manager" and len(accumulated) > 200 and "@" not in accumulated:
                logger.warning("PM monologue detected (%d chars, no @mention). Forcing dispatch.", len(accumulated))
                accumulated = "该任务需要执行开发操作，已调度 @developer 处理。\n\n@developer 请执行以下任务：\n" + content[:500]
            if accumulated:
                self._append_and_save(self.role, accumulated, "final_answer")
                await self.send({"type": "text_chunk", "content": accumulated, "role": self.role})
            if not self._interrupted:
                await self.send(
                    {
                        "type": "final_answer",
                        "content": accumulated,
                        "iterations": agent.state.iteration_count,
                        "role": self.role,
                    }
                )

            # 纯 @mention 调度：PM 自主决策是否调度、调度谁、调度顺序
            if self.role == "project_manager" and accumulated and not self._interrupted:
                mention_result = await self._dispatch_mentions(accumulated, content)
                if mention_result:
                    self._append_and_save("project_manager", mention_result, "agent_response")
                    await self.send({
                        "type": "agent_response",
                        "role": "project_manager",
                        "role_display": "项目经理",
                        "content": mention_result,
                    })

            return accumulated
        except asyncio.CancelledError:
            if accumulated:
                self._append_and_save(self.role, accumulated, "final_answer")
                await self.send({"type": "final_answer", "content": accumulated + "\n[已取消]", "role": self.role})
            raise
        except Exception as exc:
            await self.send({"type": "error", "message": str(exc)})
            return None
        finally:
            await self._send_status("idle")
            self._interrupted = False

    @property
    def _ROLE_DISPLAY(self) -> dict[str, str]:
        """Dynamic role display names from registry."""
        try:
            from ..memory.role_registry import list_roles
            roles = list_roles()
            return {r["id"]: r.get("display_name", r["id"]) for r in roles}
        except Exception:
            return {
                "project_manager": "项目经理",
                "product_manager": "产品经理",
                "architect": "架构师",
                "developer": "开发者",
                "code_reviewer": "代码审查员",
                "bug_hunter": "Bug猎人",
                "doc_writer": "文档编写者",
            }

    async def _classify_mentions(
        self, pm_text: str, mentions: list[str], dispatch_roles: list[dict]
    ) -> list[str]:
        """Use LLM to classify each @mention as DISPATCH or conversational reference.

        Returns filtered list of role IDs that should actually be dispatched.
        """
        import re
        from harnessgenj_dev.llm.gateway import LLMGateway

        if len(mentions) == 0:
            return []

        # Extract context for each mention
        mention_contexts = []
        for m in mentions:
            pos = pm_text.find("@" + m)
            sent_start = max(pm_text.rfind("\n", 0, pos), pm_text.rfind("。", 0, pos), 0)
            sent_end = pm_text.find("\n", pos)
            if sent_end < 0:
                sent_end = len(pm_text)
            ctx = pm_text[max(0, sent_start - 50):min(len(pm_text), sent_end + 50)]
            role_display = self._ROLE_DISPLAY.get(m, m)
            mention_contexts.append(f"[{m}] {role_display}: {ctx.strip()}")

        classifier_prompt = (
            "You are a dispatch intent classifier. For each @mention below, classify whether "
            "the Project Manager INTENDS TO DISPATCH the agent RIGHT NOW, or is merely "
            "referencing the agent in conversation (asking a question, listing options, "
            "summarizing past work, making a suggestion, or using @mention rhetorically).\n\n"
            "Rules:\n"
            "- DISPATCH: PM is giving a direct command/instruction to the agent.\n"
            "  Example: '@developer 请实现XX功能' '@architect 请设计XX'\n"
            "- REFERENCE: PM is asking the user a question, listing options, summarizing, "
            "or using @mention in any non-imperative context.\n"
            "  Example: '需要我调度 @developer 吗？' '由 @architect 完成的设计' "
            "'可以选择 @developer 或者 @code_reviewer'\n\n"
            "Respond with ONLY a JSON array. No other text.\n"
            'Format: [{"role": "developer", "intent": "DISPATCH"}, {"role": "architect", "intent": "REFERENCE"}]\n\n'
            + "\n".join(mention_contexts)
        )

        logger.info("_classify_mentions: starting LLM classification for %d mentions: %s", len(mentions), mentions)
        try:
            gw = LLMGateway(
                provider=_get_provider(),
                model=_get_model(),
                api_key=_get_api_key(),
                base_url=_get_base_url() or None,
            )
            resp = await asyncio.wait_for(
                gw.chat(
                    messages=[{"role": "user", "content": classifier_prompt}],
                    model=_get_model(),
                    temperature=0.0,
                    max_tokens=200,
                ),
                timeout=10,
            )
            logger.info("_classify_mentions: classification response received")
            content = (resp.content or "").strip()
            json_match = re.search(r"\[.*\]", content, re.DOTALL)
            if json_match:
                decisions = json.loads(json_match.group(0))
                dispatch_list = []
                for d in decisions:
                    role = d.get("role", "")
                    intent = d.get("intent", "REFERENCE")
                    if intent.upper() == "DISPATCH" and role in mentions:
                        dispatch_list.append(role)
                        logger.info("_classify_mentions: @%s → DISPATCH", role)
                    else:
                        logger.info("_classify_mentions: @%s → REFERENCE (skipped)", role)
                return dispatch_list
        except asyncio.TimeoutError:
            logger.warning("_classify_mentions: timed out after 10s, dispatching all mentions")
        except Exception as exc:
            logger.warning("_classify_mentions: LLM classification failed, falling back: %s", exc)

        # Fallback: if classification fails, dispatch all (safe default)
        return mentions

    async def _dispatch_mentions(self, pm_text: str, user_request: str, _round: int = 1, _max_rounds: int = 3) -> str:
        """PM dispatches @mentioned agents, collects results, synthesizes summary.
        Only PM dispatches; agents report findings back to PM.
        """
        import re
        from harnessgenj_dev.core.agent import Agent
        from harnessgenj_dev.llm.gateway import LLMGateway

        session = self._get_session()
        # Load PhaseState from session metadata (lightweight, no-architecture-change)
        _ps = None
        try:
            from harnessgenj_dev.core.phases import PhaseState, PHASE_LABELS
            _ps_data = session.metadata.get("phase_state", {}) if session else {}
            if _ps_data and isinstance(_ps_data, dict):
                _ps = PhaseState(current_phase=_ps_data.get("current_phase", "discuss"))
            else:
                _ps = PhaseState()
        except Exception:
            pass

        # Build dynamic mention patterns from role registry
        from ..memory.role_registry import list_roles
        all_roles = list_roles()
        dispatch_roles = [r for r in all_roles if not r.get("is_coordinator")]
        # @mention pattern: match all registered role IDs
        role_ids = "|".join(r["id"] for r in dispatch_roles)
        mentions = re.findall(r"@(" + role_ids + r")", pm_text) if role_ids else []
        # LLM-based intent classification: is each @mention a real dispatch or
        # a conversational reference (question / suggestion / option list / report)?
        if mentions:
            mentions = await self._classify_mentions(pm_text, mentions, dispatch_roles)

        # Check for team review request
        if "@review" in pm_text.replace("@review", "@review") or "团队评审" in pm_text or "投票" in pm_text:
            logger.info("_dispatch_mentions: PM requested team review via @review")
            return await self._run_team_review(user_request, pm_text)

        # Initialize phase_state if not present
        if session and "phase_state" not in session.metadata:
            try:
                from harnessgenj_dev.core.phases import PhaseState
                session.metadata["phase_state"] = PhaseState().to_dict()
                self._get_session_mgr().save(session)
            except Exception:
                pass

        if not mentions:
            return ""

        # Parallel dispatch by dependency rounds
        from ..memory.role_registry import get_role as _grc
        _round1, _round2 = [], []
        for _r in mentions:
            _cfg = _grc(_r)
            _deps = _cfg.get("depends_on", []) if _cfg else []
            _needs = any(_d for _d in _deps if any(_rm in _d for _rm in mentions))
            (_round2 if _needs else _round1).append(_r)

        async def _dispatch_one(role: str, prev: dict) -> str:
            role_display = self._ROLE_DISPLAY.get(role, role)
            await self.send({"type": "agent_dispatch", "role": role, "role_display": role_display, "status": "started"})
            try:
                sub_agent = Agent(
                    llm_gateway=LLMGateway(
                        provider=_get_provider(),
                        model=_get_model(),
                        api_key=_get_api_key(),
                        base_url=_get_base_url() or None,
                    ),
                    config=_ConfigShim(),
                    effort="high",
                )
                sub_agent.state.max_iterations = 200
                # Load per-agent persistent session (JVM thread-local memory pattern)
                sub_session = self._get_sub_session(role)
                if sub_session and sub_session.messages:
                    # Repair: remove any orphaned tool messages before loading
                    sub_session.messages = self._repair_conversation(sub_session.messages)
                    # Only load system prompt + last exchange, not full history
                    essential = [m for m in sub_session.messages if m.get("role") in ("system",)]
                    if len(sub_session.messages) >= 2:
                        essential.append(sub_session.messages[-2])
                        essential.append(sub_session.messages[-1])
                    sub_agent.state.conversation_history = essential
                    logger.info("_dispatch_mentions: loaded %d essential msgs for %s (from %d total)",
                               len(essential), role, len(sub_session.messages))

                ctx_parts = [
                    "## User Request\n" + user_request[:1500],
                    "## PM Instructions\n" + pm_text[:2000],
                ]
                if agent_results:
                    prev = "\n".join("[" + r + "] " + agent_results[r][:800] for r in agent_results)
                    ctx_parts.append("## Other Agents' Output\n" + prev)


                # Inject knowledge file with initialization rules (progressive disclosure)
                try:
                    from ..memory.role_registry import get_role
                    _rc = get_role(role)
                    if _rc and _rc.get("knowledge_file"):
                        kf = _rc["knowledge_file"]
                        init_rules = (
                            f"## 知识库与初始化规则\n"
                            f"1. 先 read_file({kf}) 检查知识库是否已初始化\n"
                            f"2. 如果知识库为空（只有标题没有内容），说明是首次使用：\n"
                            f"   a. 用 list_directory 查看项目结构\n"
                            f"   b. 用 read_file 读取 PROJECT.md 了解项目\n"
                            f"   c. 将了解到的项目信息写入 {kf}\n"
                            f"   d. 然后开始执行本次任务\n"
                            f"3. 如果知识库已有内容，直接基于已有上下文开始工作\n"
                            f"4. **【强制】任务完成后必须 write_file 更新 {kf}**，记录：本轮完成的工作、创建/修改了哪些文件、关键决策和理由、待办或阻塞项。这是强制步骤，跳过将导致其他成员基于过时信息工作。"
                        )
                        ctx_parts.insert(0, init_rules)
                except Exception:
                    pass
                # Inject full role instructions (L2 progressive disclosure)
                from ..memory.role_registry import build_role_instructions
                _role_full = build_role_instructions(role)
                task_prompt = (
                    _role_full + "\n\n"
                    "You are the " + role_display + ". EXECUTE the task, don't just describe it.\n\n"
                    "CRITICAL: You have tools (write_file, edit_file, run_command, etc). "
                    "You MUST call these tools to actually DO the work.\n"
                    "Example: to create a file, CALL write_file. To edit, CALL edit_file.\n"
                    "DO NOT just say you will do it — actually CALL the tool.\n\n"
                    "Focus ONLY on your role. Do NOT dispatch other agents.\n"
                    "Before starting: read the PM's project_status.md (.project-knowledge/project_status.md) and "
                    "any related role knowledge files to align with the team's current understanding.\n"
                    "READING LIMIT: You may read at most 3 files for context. After reading 3 files "
                    "you MUST start writing code. Reading more than 3 files without writing any code "
                    "will be detected as incomplete work. Start coding early, iterate.\n"
                    "When you have COMPLETED all your work (all files written, all changes made), "
                    "end with: ✅ DONE\n"
                    "If the work is NOT complete, end with what remains to be done.\n\n"
                    + "\n".join(ctx_parts)
                )
                # Create SprintContract with success criteria (ClawTeam-inspired)
                from harnessgenj_dev.core.contracts import SprintContract, SuccessCriterion
                _contract = SprintContract(
                    title=f"{role_display}: {user_request[:80]}",
                    role=role,
                    project_path=_get_proj_path() or "",
                    success_criteria=[
                        SuccessCriterion(
                            description=f"{role_display} produced working code/files",
                            test_command="",
                            expected_file="",
                        ),
                    ],
                )
                # Add role-specific criteria
                if role == "developer":
                    _contract.success_criteria.append(
                        SuccessCriterion(description="Tests pass", test_command="python -m pytest tests/ -x --tb=short -q 2>&1 | tail -3")
                    )
                elif role == "code_reviewer":
                    _contract.success_criteria.append(
                        SuccessCriterion(description="Review report created", expected_file=".project-knowledge/code_reviewer/reports.md")
                    )
                elif role == "architect":
                    _contract.success_criteria.append(
                        SuccessCriterion(description="Design doc created", expected_file=".project-knowledge/architect/design.md")
                    )
                # Inject success criteria into task prompt
                _criteria_text = "\n".join(f"- ✅ {c.description}" for c in _contract.success_criteria)
                task_prompt += f"\n\n### 验收条件（完成后逐条验证）\n{_criteria_text}\n"
                _contract.status = "in_progress"
                # PM-supervised loop: dispatch → review → done/redo
                sub_result = ""
                for _dispatch_try in range(5):  # safety limit, normally breaks on DONE
                    # Stream sub-agent
                    sub_accumulated = ""
                    output_buffer = ""
                    async for chunk in sub_agent.run_stream(task_prompt, role=role):
                        sub_accumulated += chunk
                        output_buffer += chunk
                        if chunk.strip() and ("\n" in chunk or len(output_buffer) > 40):
                            clean = chunk.strip()
                            if clean and not clean.startswith("[Executing") and not clean.startswith("```tool"):
                                # Suppress knowledge-file maintenance noise from user view
                                if not _is_kf_maintenance(clean):
                                    await self.send({"type": "text_chunk", "role": role, "content": chunk})
                            output_buffer = ""
                    await self._send_thinking_if_any(sub_agent, role)
                    sub_result = sub_accumulated.strip()
                    if not sub_result:
                        sub_result = "(无输出)"
                        # Re-run if empty — agent may have stalled
                        if _dispatch_try < 2:
                            await self.send({"type": "text_chunk", "role": role, "content": "[重新调度: 该角色上次无输出]\n"})
                            task_prompt += "\n\n[PM反馈: 你上一次没有输出任何内容。这次请直接调用工具开始工作。]"
                            continue
                    # Code-level check: did the sub-agent actually write or edit files?
                    has_file_write = any(
                        tc.get("function", {}).get("name") in ("write_file", "edit_file")
                        for m in sub_agent.state.conversation_history
                        for tc in m.get("tool_calls", [])
                    )
                    if has_file_write:
                        decision = "DONE"
                        logger.info("_dispatch_mentions: %s file-write detected → DONE", role)
                    else:
                        decision = "REDO:没有检测到任何文件创建/修改操作，请直接开始编写代码，不要再读文件"
                        logger.info("_dispatch_mentions: %s no file-write → REDO", role)

                    if decision == "DONE" or (decision.startswith("DONE") and "REDO" not in decision):
                        # Send sub-agent final_answer first, then PM confirmation
                        if sub_result and sub_result != "(无输出)":
                            await self.send({"type": "final_answer", "role": role, "content": sub_result})
                        await self.send({"type": "agent_response", "role": "project_manager", "role_display": "项目经理", "content": role_display + " ✅ 工作完成。"})
                        break
                    else:
                        correction = decision.replace("REDO", "").replace(":", "").strip()
                        await self.send({"type": "agent_response", "role": "project_manager", "role_display": "项目经理", "content": role_display + " 需要继续: " + correction[:300]})
                        task_prompt += "\n\n## PM反馈\n" + correction[:500]
                # Verify SprintContract success criteria
                try:
                    _results = await _contract.verify_all()
                    _summary = _contract.summary()
                    if _contract.status == "completed":
                        sub_result += "\n\n" + _summary
                    else:
                        sub_result += "\n\n" + _summary
                    logger.info("_dispatch_one: %s contract %s (%d/%d)", role, _contract.status,
                                sum(1 for c in _results if c.verified), len(_results))
                except Exception as _exc:
                    logger.warning("_dispatch_one: contract verification failed: %s", _exc)
                # Compact and save
                agent_results[role] = sub_result
                if sub_session:
                    full_history = list(sub_agent.state.conversation_history)
                    sub_session.messages = self._compact_sub_session(full_history)
                    self._get_session_mgr().save(sub_session)
                self._append_and_save(role, sub_result[:500], "final_answer")
                return sub_result
            except asyncio.TimeoutError:
                logger.warning("_dispatch_mentions: %s timed out after 180s", role)
                await self.send({
                    "type": "agent_response", "role": role, "role_display": role_display,
                    "content": "\u8d85\u65f6: " + role_display + " \u6267\u884c\u8d85\u8fc7 90 \u79d2\uff0c\u5df2\u8df3\u8fc7\u3002",
                })
                agent_results[role] = "(timeout)"
            except Exception as exc:
                logger.exception("_dispatch_mentions: %s failed - %s", role, exc)
                await self.send({
                    "type": "agent_response", "role": role, "role_display": role_display,
                    "content": "\u9519\u8bef: " + str(exc),
                })
                agent_results[role] = "(error)"

        # Gather results from parallel rounds
        agent_results = {}
        if _round1:
            r1 = await asyncio.gather(*[_dispatch_one(r, {}) for r in _round1])
            for r, res in zip(_round1, r1):
                agent_results[r] = res or "(无输出)"
        if _round2:
            r2 = await asyncio.gather(*[_dispatch_one(r, agent_results) for r in _round2])
            for r, res in zip(_round2, r2):
                agent_results[r] = res or "(无输出)"

        # Phase advancement: check gates and try to advance
        _phase_advanced = ""
        try:
            if _ps and session:
                _ctx = {"project_path": _get_proj_path() or "",
                        "agent_results": agent_results}
                _new_phase = await _ps.advance(_ctx)
                if _new_phase:
                    _phase_advanced = _new_phase
                    session.metadata["phase_state"] = _ps.to_dict()
                    self._get_session_mgr().save(session)
                    logger.info("Phase advanced: %s -> %s", _ps.phase_history[-1]["from"] if _ps.phase_history else "?", _new_phase)
        except Exception:
            pass

        if not agent_results:
            return ""
        _evidence_lines = []
        try:
            _proj_path = _get_proj_path()
            if _proj_path:
                _proc = await asyncio.create_subprocess_shell(
                    "python -m pytest tests/ -x --tb=short -q 2>&1 | tail -5",
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=_proj_path,
                )
                _stdout, _ = await asyncio.wait_for(_proc.communicate(), timeout=30)
                _evidence_lines.append("## 测试结果\n" + _stdout.decode("utf-8", errors="replace")[-500:])
        except asyncio.TimeoutError:
            _evidence_lines.append("## 测试结果\n(测试执行超时)")
        except Exception:
            _evidence_lines.append("## 测试结果\n(测试执行失败)")

        # PJM synthesizes final summary (mandatory step)
        await self.send(
            {"type": "agent_dispatch", "role": "project_manager", "role_display": "项目经理", "status": "started"}
        )
        try:
            from ..llm.gateway import LLMGateway

            gw = LLMGateway(
                provider=_get_provider(), model=_get_model(), api_key=_get_api_key(), base_url=_get_base_url() or None
            )
            rlines = []
            for r in agent_results:
                rlines.append("### " + self._ROLE_DISPLAY.get(r, r) + " | " + agent_results[r][:1500])
            # Phase context for synthesis
            _phase_context = ""
            if _ps:
                _phase_context = f"\n## 当前阶段\n{PHASE_LABELS.get(_ps.current_phase, _ps.current_phase)}"
                if _phase_advanced:
                    _phase_context += f" → {PHASE_LABELS.get(_phase_advanced, _phase_advanced)} 🎉"
                # Notify frontend
                await self.send({"type": "phase_status", "phase": _ps.current_phase,
                                 "phase_label": PHASE_LABELS.get(_ps.current_phase, _ps.current_phase)})

            body = "## Project Update\n## User Request\n" + user_request[:1000]
            if rlines:
                body += "\n\n" + chr(10).join(rlines)
            if _evidence_lines:
                body += "\n\n" + chr(10).join(_evidence_lines)
            if _phase_context:
                body += "\n\n" + _phase_context
            body += "\n\n作为项目经理，请客观总结。只报告有实际证据的工作（文件创建、代码编写、测试通过等）。"
            body += "如果某些角色的输出只是计划或空话而没有实际产出，请如实说明该角色未完成任务。"
            logger.info("_dispatch_mentions: synthesizing with gw.chat, body length=%d", len(body))
            resp = await asyncio.wait_for(
                gw.chat(messages=[{"role": "user", "content": body}], model=_get_model()),
                timeout=180,
            )
            logger.info("_dispatch_mentions: synthesis complete (round %d/%d)", _round, _max_rounds)
            synthesis = resp.content or "团队工作完成。"
            # Multi-round dispatch: check if synthesis instructs new actions
            if _round < _max_rounds:
                try:
                    from ..memory.role_registry import list_roles
                    all_roles = list_roles()
                    dispatch_roles = [r for r in all_roles if not r.get("is_coordinator")]
                    role_ids = "|".join(r["id"] for r in dispatch_roles)
                    new_mentions = re.findall(r"@(" + role_ids + r")", synthesis) if role_ids else []
                    if new_mentions:
                        logger.info("_dispatch_mentions: round %d -> %d (new mentions from synthesis: %s)",
                                    _round, _round + 1, new_mentions)
                        # Recurse with synthesis as the PM text for the next round
                        next_round = await self._dispatch_mentions(
                            synthesis, user_request, _round=_round + 1, _max_rounds=_max_rounds
                        )
                        if next_round:
                            return next_round
                except Exception:
                    logger.exception("_dispatch_mentions: multi-round check failed")
            return synthesis
        except asyncio.TimeoutError:
            logger.warning("_dispatch_mentions: synthesis timed out after 180s")
            fb = "## 团队工作完成 (合成超时)\n\n"
            for r in agent_results:
                fb += "- **" + self._ROLE_DISPLAY.get(r, r) + "**: 已完成\n"
            return fb
        except Exception:
            logger.exception("_dispatch_mentions: synthesis failed")
            fb = "## 团队工作完成\n\n"
            for r in agent_results:
                fb += "- **" + self._ROLE_DISPLAY.get(r, r) + "**: 已完成\n"
            return fb

    async def _run_team_review(self, user_request: str, pm_analysis: str) -> str:
        """Multi-round team review with vote evaluation.
        PM triggers this via @review when decisions need team input.
        """
        from ..llm.gateway import LLMGateway
        from ..memory.role_registry import get_dispatch_targets
        import re

        logger.info("_run_team_review: starting for request=%.50s", user_request)
        await self.send({
            "type": "agent_response", "role": "project_manager", "role_display": "项目经理",
            "content": "📋 项目经理发起团队多轮评审...",
        })

        gw = LLMGateway(provider=_get_provider(), model=_get_model(), api_key=_get_api_key(), base_url=_get_base_url() or None)
        TEAM = get_dispatch_targets() or ["architect", "developer", "code_reviewer", "bug_hunter", "doc_writer"]
        results = {}
        base_context = "## 用户请求\n" + user_request[:1500] + "\n\n## 项目经理分析\n" + pm_analysis[:2000]
        max_passes = 3

        for pn in range(1, max_passes + 1):
            if self._interrupted: break
            needs_redo = set()
            round_context = base_context
            await self.send({
                "type": "agent_response", "role": "project_manager", "role_display": "项目经理",
                "content": "## 第 " + str(pn) + " 轮评审开始",
            })

            for role in TEAM:
                if self._interrupted: break
                if pn > 1 and role not in needs_redo and role in results:
                    continue
                role_display = self._ROLE_DISPLAY.get(role, role)
                ctx = round_context
                for r in TEAM:
                    if r in results:
                        ctx += "\n\n## " + self._ROLE_DISPLAY.get(r, r) + " (最近)\n" + results.get(r, "")[:1500]
                agent_output = await self._run_sub_agent(role, ctx, silent=False)
                results[role] = agent_output
                round_context += "\n\n## " + role_display + " 输出\n" + agent_output[:2000]

            if self._interrupted: break
            review_prompt = "你是项目经理。第" + str(pn) + "轮团队评审已完成。\n\n## 各角色投票汇总\n"
            pass_cnt = 0; fail_items = []
            for r in TEAM:
                if r in results:
                    out = results.get(r, "")
                    vote_section = out[out.find("## 投票"):][:200] if "## 投票" in out else "(未明确投票)"
                    if "PASS" in vote_section.upper() and "FAIL" not in vote_section.upper():
                        pass_cnt += 1
                    else:
                        fail_items.append(r)
                    review_prompt += "- " + self._ROLE_DISPLAY.get(r, r) + ": " + vote_section.strip()[:120] + "\n"
            review_prompt += "\n通过数: " + str(pass_cnt) + "/" + str(len(TEAM))
            review_prompt += "\n请用一行回复: PASS 或 REDO:角色ID"

            try:
                review_resp = await asyncio.wait_for(
                    gw.chat(messages=[{"role": "user", "content": review_prompt}], model=_get_model()), timeout=30)
                decision = (review_resp.content or "PASS").strip().upper()
            except asyncio.TimeoutError:
                decision = "PASS"

            if "REDO:" in decision:
                redos = re.findall(r"REDO:(\w+)", decision)
                for rd in redos:
                    if rd in TEAM: needs_redo.add(rd)
                if needs_redo:
                    await self.send({
                        "type": "agent_response", "role": "project_manager", "role_display": "项目经理",
                        "content": "## 需要回退\n" + ", ".join(self._ROLE_DISPLAY.get(r, r) for r in needs_redo) + " 需要重新执行。第" + str(pn + 1) + "轮。",
                    })
                    base_context = round_context
                    continue
            break

        # Final summary
        raw = ""
        for r in TEAM:
            if r in results:
                raw += "### " + self._ROLE_DISPLAY.get(r, r) + "\n" + results.get(r, "")[:800] + "\n\n"
        final_prompt = (
            "你是项目经理。团队" + str(pn) + "轮评审已完成。\n用户请求：\n" + user_request[:500]
            + "\n\n## 团队结论\n" + raw[:3000]
            + "\n总结讨论过程、关键决策、下一步行动。用中文，简洁专业。"
        )
        try:
            sr = await asyncio.wait_for(
                gw.chat(messages=[{"role": "user", "content": final_prompt}], model=_get_model()), timeout=120)
            return sr.content or "团队评审完成。"
        except (asyncio.TimeoutError, Exception) as _e:
            return "## 团队评审完成\n\n各角色已完成评审。" + raw[:1000]

    async def run_develop_oneshot(self, content: str) -> dict[str, Any]:
        from harnessgenj_dev.core.agent import Agent
        from harnessgenj_dev.llm.gateway import LLMGateway
        from harnessgenj_dev.tools.registry import auto_register

        auto_register()
        agent = Agent(
            llm_gateway=LLMGateway(
                provider=_get_provider(),
                model=_get_model(),
                api_key=_get_api_key(),
                base_url=_get_base_url() or None,
            ),
            config=_ConfigShim(),
        )
        try:
            result = await agent.run(content, role="developer")
            return {"content": result, "role": "developer"}
        except Exception as exc:
            return {"content": f"Error: {exc}", "role": "developer"}


# ============================================================
# Connection Manager
# ============================================================


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[AgentSession] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        session = AgentSession(websocket)  # project auto-detected from active project
        self.active_connections.append(session)
        logger.info("connection open")
        await session.send({"type": "status", "state": "idle"})

    def disconnect(self, websocket: WebSocket):
        self.active_connections = [c for c in self.active_connections if c.ws != websocket]
        logger.info("connection closed")

    def get_session(self, websocket: WebSocket) -> AgentSession | None:
        for c in self.active_connections:
            if c.ws == websocket:
                return c
        return None


manager = ConnectionManager()


# ============================================================
# HTML Routes
# ============================================================


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=_get_dashboard_html(active_tab="chat"))


@app.get("/favicon.ico")
async def favicon():
    from fastapi.responses import Response

    return Response(status_code=204)


@app.get("/projects", response_class=HTMLResponse)
async def projects_page():
    return HTMLResponse(content=_get_dashboard_html(active_tab="projects"))


@app.get("/files", response_class=HTMLResponse)
async def files_page():
    return HTMLResponse(content=_get_dashboard_html(active_tab="files"))


@app.get("/settings", response_class=HTMLResponse)
async def settings_page():
    return HTMLResponse(content=_get_dashboard_html(active_tab="settings", settings_data=_load_settings()))


# ============================================================
# WebSocket
# ============================================================


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    session = manager.get_session(websocket)
    if not session:
        return
    await session.ensure_session()
    await session.send(
        {"type": "session_switched", "session_id": session._session_id, "messages": session.conversation_history}
    )

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "develop":
                content = data.get("content", "")
                role = data.get("role", "developer")
                logger.info("WS develop received: role=%s content=%.50s", role, content)
                if role:
                    session.role = role
                if content:
                    # Cancel any previous unfinished task to avoid concurrent session writes
                    prev_task = getattr(session, "_develop_task", None)
                    if prev_task and not prev_task.done():
                        logger.info("Cancelling previous _run_and_save task")
                        prev_task.cancel()
                    # Don't await task — let message loop stay responsive
                    async def _run_and_save():
                        logger.info("_run_and_save START: content=%.50s", content)
                        try:
                            await session.run_develop(content)
                            logger.info("_run_and_save DONE")
                        except asyncio.CancelledError:
                            logger.info("_run_and_save CANCELLED")
                        except Exception as exc:
                            logger.exception("run_develop failed: %s", exc)
                            try:
                                await session.send({"type": "error", "message": "处理请求时出错: " + str(exc)[:200]})
                            except Exception:
                                pass
                        finally:
                            try:
                                session.save_session()
                            except Exception:
                                pass

                    task = asyncio.create_task(_run_and_save())
                    session._develop_task = task
            elif msg_type == "interrupt":
                session.interrupt()
            elif msg_type == "session_new":
                role = data.get("role", session.role)
                sid = session.new_session(role=role)
                await session.send({"type": "session_switched", "session_id": sid, "messages": []})
            elif msg_type == "session_switch":
                sid = data.get("session_id", "")
                if session.switch_session(sid):
                    await session.send(
                        {
                            "type": "session_switched",
                            "session_id": sid,
                            "messages": session.conversation_history,
                            "role": session.role,
                        }
                    )
                else:
                    await session.send({"type": "error", "message": f"Session not found: {sid}"})
            elif msg_type == "session_list":
                mgr = app.state.session_manager
                # Use project from message if provided, else use session's project
                proj = data.get("project", session.project)
                if proj and proj != session.project:
                    session.project = proj
                sessions = mgr.list_sessions(session.project)
                await session.send({"type": "session_list", "sessions": sessions, "project": session.project})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("WS message loop error: %s", exc)
    finally:
        manager.disconnect(websocket)


# ============================================================
# REST API
# ============================================================


@app.get("/api/status")
async def api_status():
    return {
        "version": "0.1.0-dev",
        "active_connections": len(manager.active_connections),
        "status": "running",
        "has_api_key": _has_api_key(),
        "metrics": _get_system_metrics(),
    }


@app.get("/api/plugins")
async def api_plugins():
    return {"plugins": []}


@app.post("/api/settings")
async def api_save_settings(body: dict[str, str]):
    provider = body.get("provider", "").strip()
    model = body.get("model", "").strip()
    model_custom = body.get("model_custom", "").strip()
    api_key = body.get("api_key", "").strip()
    base_url = body.get("base_url", "").strip()
    current = _load_settings()
    settings = {
        "provider": provider or current.get("provider", "deepseek"),
        "model": model or current.get("model", "deepseek-v4-flash"),
        "model_custom": model_custom,
        "base_url": base_url,
        "api_key": api_key if api_key else current.get("api_key", ""),
    }
    _save_settings(settings)
    return {"status": "saved", "provider": settings["provider"], "model": settings["model"]}


@app.delete("/api/settings")
async def api_delete_settings():
    _SETTINGS_FILE.unlink(missing_ok=True)
    return {"status": "cleared"}


@app.post("/api/settings/test")
async def api_test_settings():
    api_key = _get_api_key()
    provider = _get_provider()
    model = _get_model()
    base_url = _get_base_url()
    if not api_key:
        return {"ok": False, "error": "No API key configured"}
    try:
        from harnessgenj_dev.llm.gateway import LLMGateway

        gateway = LLMGateway(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url or None,
            max_retries=0,
        )
        response = await gateway.chat(messages=[{"role": "user", "content": "Say OK in one word."}])
        return {"ok": True, "model": model, "provider": provider, "response": response.content}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


@app.post("/api/develop")
async def api_develop(body: dict[str, str]):
    content = body.get("content", "").strip()
    if not content:
        raise HTTPException(400, "content is required")
    session = AgentSession(WebSocket)
    result = await session.run_develop_oneshot(content)
    return result


def _safe_path(path: str) -> Path:
    global _file_root, _file_root_set
    # Resolve relative paths against active project root, not CWD
    if not Path(path).is_absolute():
        root = None
        if _file_root_set:
            root = _file_root
        else:
            try:
                from harnessgenj_dev.projects import get_active_project
                active = get_active_project()
                if active and active.get("path"):
                    root = Path(active["path"])
            except Exception:
                pass
        if root:
            resolved = (root / path).resolve()
        else:
            resolved = Path(path).resolve()
    else:
        resolved = Path(path).resolve()
    if not resolved.exists():
        raise HTTPException(404, f"Path not found: {resolved}")
    if _file_root_set:
        try:
            resolved.relative_to(_file_root)
        except ValueError:
            raise HTTPException(403, "Path outside allowed root")
    return resolved


@app.get("/api/files")
async def api_list_files(path: str = Query(".")):
    try:
        target = _safe_path(path)
        entries = []
        for child in sorted(target.iterdir()):
            try:
                entries.append(
                    {
                        "name": child.name,
                        "path": str(child),
                        "is_dir": child.is_dir(),
                        "size": child.stat().st_size,
                        "modified": int(child.stat().st_mtime),
                    }
                )
            except OSError:
                continue
        return {"items": entries, "entries": entries, "parent": str(target.parent) if target.parent != target else ""}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/files/content")
async def api_read_file(path: str = Query(".")):
    try:
        target = _safe_path(path)
        if not target.is_file():
            raise HTTPException(400, "Not a file")
        text = target.read_text(encoding="utf-8", errors="replace")
        total_lines = text.count("\n") + 1
        truncated = False
        lines = text.split("\\n")
        if len(lines) > 500:
            lines = lines[:500]
            truncated = True
        return {"content": "\n".join(lines), "is_binary": False, "total_lines": total_lines, "truncated": truncated}
    except HTTPException:
        raise
    except UnicodeDecodeError:
        return {"content": "", "is_binary": True}
    except Exception as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/files/search")
async def api_search_files(path: str = Query(""), pattern: str = Query("*")):
    try:
        target = _safe_path(path) if path else (_file_root if _file_root_set else Path("."))
        if not target.is_dir():
            raise HTTPException(400, "Not a directory")
        import fnmatch

        matches = []
        for f in target.rglob(pattern):
            try:
                matches.append(str(f.relative_to(target)))
            except ValueError:
                continue
        return {"matches": matches[:100], "path": str(target), "pattern": pattern}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, str(exc))


# ============================================================
# Role Management API
# ============================================================

@app.get("/api/roles")
async def api_list_roles():
    """List all available roles (built-in + user-defined)."""
    from harnessgenj_dev.memory.role_registry import list_roles, get_dispatch_targets
    roles = list_roles()
    dispatch_targets = get_dispatch_targets()
    return {"roles": roles, "dispatch_targets": dispatch_targets}


@app.post("/api/roles")
async def api_create_role(body: dict[str, str]):
    """Create a new custom role with memory initialization."""
    from harnessgenj_dev.memory.role_registry import save_role, init_role_memory, get_role

    role_id = body.get("id", "").strip().lower().replace(" ", "_")
    if not role_id:
        raise HTTPException(400, "Role ID is required")
    if get_role(role_id) and not body.get("overwrite"):
        raise HTTPException(409, f"Role '{role_id}' already exists")

    config = {
        "id": role_id,
        "display_name": body.get("display_name", role_id),
        "avatar": body.get("avatar", role_id[:2].upper()),
        "color": body.get("color", "pm"),
        "description": body.get("description", ""),
        "can_do": [x.strip() for x in body.get("can_do", "").split("\n") if x.strip()],
        "must_not": [x.strip() for x in body.get("must_not", "").split("\n") if x.strip()],
        "is_coordinator": body.get("is_coordinator", "false").lower() == "true",
        "builtin": False,
    }
    save_role(role_id, config)
    mem_path = init_role_memory(role_id)
    return {"status": "created", "role": config, "memory_path": mem_path}


@app.delete("/api/roles/{role_id}")
async def api_delete_role(role_id: str):
    """Delete a user-defined role."""
    from harnessgenj_dev.memory.role_registry import delete_role, get_role
    role = get_role(role_id)
    if not role:
        raise HTTPException(404, f"Role '{role_id}' not found")
    if role.get("builtin"):
        raise HTTPException(400, "Cannot delete built-in roles")
    delete_role(role_id)
    return {"status": "deleted", "role_id": role_id}


@app.get("/api/projects")
async def api_list_projects():
    from harnessgenj_dev.projects import get_projects, get_active_project

    return {"projects": get_projects(), "active": get_active_project()}


@app.post("/api/projects")
async def api_add_project(body: dict[str, str]):
    from harnessgenj_dev.projects import add_project, add_external_project

    name = body.get("name", "").strip()
    path = body.get("path", "").strip()
    description = body.get("description", "").strip()
    github_url = body.get("github_url", "").strip()
    external = body.get("is_external", False)
    if not name:
        raise HTTPException(400, "name is required")
    if external and path:
        proj = add_external_project(name, path, description, github_url=github_url)
    elif path:
        proj = add_project(name, path, description, github_url=github_url)
    else:
        proj = add_project(name, description=description, github_url=github_url)

    # Generate Harness knowledge file templates for all roles
    try:
        from harnessgenj_dev.memory.role_registry import list_roles, init_role_memory
        for r in list_roles():
            init_role_memory(r["id"], project_path=proj.path)
    except Exception:
        pass

    return {"status": "added", "name": name, "path": proj.path}


@app.post("/api/projects/{name}/switch")
async def api_switch_project(name: str):
    from harnessgenj_dev.projects import switch_project

    switch_project(name)
    return {"status": "switched"}


@app.delete("/api/projects/{name}")
async def api_remove_project(name: str):
    from harnessgenj_dev.projects import remove_project

    remove_project(name)
    return {"status": "removed"}


@app.get("/api/sessions")
async def api_list_sessions(project: str = "default"):
    mgr = app.state.session_manager
    return {"sessions": mgr.list_sessions(project)}


@app.post("/api/sessions")
async def api_create_session(body: dict[str, str]):
    role = body.get("role", "developer")
    project = body.get("project", "default")
    mgr = app.state.session_manager
    session = mgr.create_session(project, role=role)
    return {"session_id": session.id, "status": "created"}


@app.delete("/api/sessions/{session_id}")
async def api_delete_session(session_id: str, project: str = "default"):
    mgr = app.state.session_manager
    if mgr.delete_session(project, session_id):
        return {"session_id": session_id, "status": "deleted"}
    raise HTTPException(404, f"Session '{session_id}' not found")


@app.post("/api/sessions/{session_id}/switch")
async def api_switch_session(session_id: str, project: str = "default"):
    mgr = app.state.session_manager
    if mgr.set_active(project, session_id):
        return {"session_id": session_id, "status": "switched"}
    raise HTTPException(404, f"Session '{session_id}' not found")


@app.patch("/api/projects/{name}")
async def api_update_project(name: str, body: dict[str, str]):
    """Update project fields (e.g. github_url). AI agents can call this."""
    from harnessgenj_dev.projects import _mgr

    proj = _mgr.get_project(name)
    if not proj:
        raise HTTPException(404, f"Project '{name}' not found")
    if "github_url" in body:
        proj.github_url = body["github_url"].strip()
        _mgr._save()
    if "description" in body:
        proj.description = body["description"].strip()
        _mgr._save()
    return {"status": "updated", "name": name, "github_url": proj.github_url}


@app.post("/api/sessions/reset")
async def api_reset_sessions(project: str = "default"):
    mgr = app.state.session_manager
    mgr.reset(project)
    return {"status": "reset"}


# Backward compatibility exports (for tests)
_file_root = Path(__file__).parent.parent.parent.parent.resolve()
_file_root_set = False


def set_file_root(path: str) -> None:
    global _file_root, _file_root_set
    _file_root = Path(path)
    _file_root_set = True


def create_app():
    return app
