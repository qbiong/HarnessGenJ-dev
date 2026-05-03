"""Web Dashboard - FastAPI server with WebSocket streaming and REST APIs."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)


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
.tab-section {{ display: none; width: 100%; height: 100%; overflow: hidden; }}
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
</style>
</head>
<body>

<!-- Top Navigation -->
<nav class="topnav">
    <div class="topnav-brand">HGJ-dev</div>
    <span style="flex:1"></span>
    <div class="topnav-tabs">
        <a class="topnav-tab{' active' if active_tab == 'chat' else ''}" onclick="switchTab('chat')">对话</a>
        <a class="topnav-tab{' active' if active_tab == 'projects' else ''}" onclick="switchTab('projects')">项目</a>
        <a class="topnav-tab{' active' if active_tab == 'files' else ''}" onclick="switchTab('files')">文件</a>
        <a class="topnav-tab{' active' if active_tab == 'settings' else ''}" onclick="switchTab('settings')">设置</a>
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
<div class="tab-section{' active' if active_tab == 'chat' else ''}" id="tab-chat">
    <div class="session-bar">
        <select class="role-select" id="project-select" onchange="switchActiveProject()">
            <option value="">加载中...</option>
        </select>
        <span style="font-size:11px;color:var(--text-muted)">|</span>
        <span style="font-size:11px;color:var(--accent-cyan);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:300px;" id="project-info"></span>
        <span style="font-size:11px;color:var(--text-muted)">|</span>
        <select class="role-select" id="role-select">
            <option value="project_manager" selected>Project Manager</option>
                    <option value="product_manager">Product Manager</option>
            <option value="developer">Developer</option>
            <option value="code_reviewer">Code Reviewer</option>
            <option value="bug_hunter">Bug Hunter</option>
            <option value="architect">Architect</option>
            <option value="doc_writer">Doc Writer</option>
        </select>
        <span style="font-size:11px;color:var(--text-muted)">|</span>
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
                <p>AI 驱动的开发助手</p>
                <p style="margin-top:8px;font-size:12px;color:var(--text-muted);">输入请求开始开发</p>
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
<div class="tab-section{' active' if active_tab == 'projects' else ''}" id="tab-projects">
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
                <button class="btn btn-secondary" onclick="addExternalProject()" style="align-self:flex-end;margin-bottom:1px;">打开外部项目</button>
            </div>
        </div>
    </div>
</div>

<!-- ===== Files Section ===== -->
<div class="tab-section{' active' if active_tab == 'files' else ''}" id="tab-files">
    <div class="files-container">
        <h2>文件浏览器</h2>
        <div id="file-listing"></div>
        <pre class="file-viewer" id="file-viewer"></pre>
    </div>
</div>

<!-- ===== Settings Section ===== -->
<div class="tab-section{' active' if active_tab == 'settings' else ''}" id="tab-settings">
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
                <p style="margin-top:6px;">API 密钥: <span id="s-current-key" style="color:var(--text-primary);">{'sk-' + _get_api_key()[:6] + '...' if _get_api_key() else '未设置'}</span></p>
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
        if (el.textContent.trim() === ['对话','项目','文件','设置'][['chat','projects','files','settings'].indexOf(tab)]) el.classList.add('active');
    }});
    if (tab === 'projects') loadProjects();
    if (tab === 'files') listDir('');
}}
// Support hash-based deep links
var tabFromHash = {{'#chat':'chat','#projects':'projects','#files':'files','#settings':'settings'}}[location.hash];
if (tabFromHash) switchTab(tabFromHash);

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
    ws.onclose = function() {{
        console.log('WS disconnected, reconnecting in 2s...');
        setTimeout(connect, 2000);
    }};
}}
connect();

function handleMessage(msg) {{
    switch (msg.type) {{
        case 'status':
            if (msg.state === 'running') {{ statusDot.className = 'status-dot running'; statusText.textContent = '运行中'; btnSend.style.display = 'none'; btnStop.style.display = ''; }}
            else {{ statusDot.className = 'status-dot idle'; statusText.textContent = '就绪'; btnSend.style.display = ''; btnStop.style.display = 'none'; }}
            break;
        case 'text_chunk':
            var lastMsg = chat.querySelector('.msg-group.ai:last-child');
            if (!lastMsg) {{
                var div = document.createElement('div');
                div.className = 'msg-group ai';
                div.innerHTML = renderMsg(msg.role || 'project_manager', 'ai', '');
                chat.appendChild(div);
                lastMsg = div;
            }}
            lastMsg.querySelector('.msg-bubble').innerHTML += escapeHtml(msg.content);
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
                var lastAi = chat.querySelector('.msg-group.ai:last-child');
                if (lastAi) {{
                    lastAi.querySelector('.msg-bubble').innerHTML = formatContent(msg.content);
                }} else {{
                    addAiMsg(msg.content, msg.role || 'project_manager');
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
        case 'session_switched':
            currentSessionId = msg.session_id;
            if (msg.messages) {{
                chat.innerHTML = '';
                for (var m of msg.messages) {{
                    if (m.role === 'user') addMsg('user', m.content);
                    else if (m.role === 'assistant') addMsg('ai', m.content, 'project_manager');
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
    var mentionMatch = text.match(/@(product_manager|architect|developer|code_reviewer|bug_hunter|doc_writer)/);
    var targetRole = mentionMatch ? mentionMatch[1] : roleSelect.value;
    var content = mentionMatch ? text.replace(mentionMatch[0], '').trim() : text;

    if (ws && ws.readyState === WebSocket.OPEN) {{
        ws.send(JSON.stringify({{type: 'develop', content: content || text, role: targetRole}}));
    }}
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
    try {{ return marked.parse(text); }} catch(e) {{ return escapeHtml(text); }}
}}

function escapeHtml(text) {{
    var d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}}

function renderMsg(role, className, content) {{
    var roles = {{'project_manager':{{'av':'PJM','nm':'项目经理','cl':'pjm'}},'product_manager':{{'av':'PM','nm':'产品经理','cl':'pm'}},'architect':{{'av':'AR','nm':'架构师','cl':'arch'}},'developer':{{'av':'DV','nm':'开发者','cl':'dev'}},'code_reviewer':{{'av':'RV','nm':'审查员','cl':'rev'}},'bug_hunter':{{'av':'BH','nm':'Bug猎人','cl':'hunt'}},'doc_writer':{{'av':'DW','nm':'文档编写者','cl':'doc'}}}};
    var r = roles[role] || {{'av':'AI','nm':role,'cl':'pm'}};
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
            '<div class="s-title">' + escapeHtml(s.title || '新对话') + '</div>' +
            '<div class="s-meta">' + (s.message_count||0) + ' 条消息' + (time ? ' · ' + time : '') + '</div>' +
            '<div class="s-actions"><a onclick="event.stopPropagation();deleteSession(\\''+s.id+'\\')">删除</a></div></div>';
    }}).join('');
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
        await fetch('/api/sessions/' + sid, {{method:'DELETE'}});
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
        var html = '<table class="projects-table"><tr><th>名称</th><th>路径</th><th>类型</th><th>描述</th><th>状态</th><th>操作</th></tr>';
        for (var p of data.projects) {{
            var typeTag = p.is_external ? '<span style=\"color:var(--accent-cyan);font-size:10px;\">📂 外部</span>' : '<span style=\"color:var(--success);font-size:10px;\">🏠 工作区</span>';
            var desc = p.description || '<span style=\"color:var(--text-muted);font-size:10px;\">无描述</span>';
            var activeBadge = p.active ? ' style=\"background:var(--bg-tertiary)\"' : '';
            var switchBtn = p.active ? '<span style=\"color:var(--success);font-size:11px;\">✓ 当前</span>' : '<button class=\"btn btn-secondary\" style=\"padding:3px 8px;font-size:11px;background:var(--accent-cyan);color:#000;border:none;\" onclick=\"switchProject(\\''+escapeHtml(p.name)+'\\')\">切换</button>';
            html += '<tr' + activeBadge + '>';
            html += '<td style=\"font-weight:600;\">' + escapeHtml(p.name) + '</td>';
            html += '<td style=\"font-size:11px;font-family:var(--font-mono);\">' + escapeHtml(p.path) + '</td>';
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
    if (!name) {{ alert('请输入项目名称'); return; }}
    var body = {{name: name, description: desc}};
    await fetch('/api/projects', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(body)}});
    document.getElementById('pname').value = '';
    document.getElementById('pdesc').value = '';
    loadProjects();
    loadProjectsDropdown();
}}

async function addExternalProject() {{
    var name = document.getElementById('epname').value.trim();
    var path = document.getElementById('eppath').value.trim();
    var desc = document.getElementById('epdesc').value.trim();
    if (!name || !path) {{ alert('请输入项目名称和路径'); return; }}
    var body = {{name: name, path: path, description: desc, is_external: true}};
    await fetch('/api/projects', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(body)}});
    document.getElementById('epname').value = '';
    document.getElementById('eppath').value = '';
    document.getElementById('epdesc').value = '';
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
    try {{
        var r = await fetch('/api/files/content?path=' + encodeURIComponent(path));
        var data = await r.json();
        var v = document.getElementById('file-viewer');
        v.textContent = data.is_binary ? '[Binary file]' : (data.content || '');
        v.style.display = 'block';
    }} catch(e) {{}}
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
}});
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
    yield


app.router.lifespan_context = lifespan


# ============================================================
# Agent Session
# ============================================================

_DEFAULT_TEAM_ROLE = "project_manager"


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
                provider=_get_provider(), model=_get_model(),
                api_key=_get_api_key(), base_url=_get_base_url() or None,
            )
            self._agent = Agent(llm_gateway=gateway, config=_ConfigShim())
        return self._agent

    def _inject_role_memory(self, agent, role: str) -> None:
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

    def interrupt(self) -> None:
        self._interrupted = True
        if self._develop_task:
            self._develop_task.cancel()

    async def send(self, data: dict) -> None:
        try:
            await self.ws.send_json(data)
        except Exception:
            pass

    async def _send_status(self, state: str) -> None:
        await self.send({"type": "status", "state": state})

    async def _run_sub_agent(self, role: str, context: str, parent_role: str = "product_manager") -> str:
        """Run a sub-agent with given role and context. Returns response text."""
        from harnessgenj_dev.core.agent import Agent
        from harnessgenj_dev.llm.gateway import LLMGateway
        role_display = self._ROLE_DISPLAY.get(role, role)
        await self.send({"type": "agent_dispatch", "role": role, "role_display": role_display, "status": "started"})
        try:
            sub = Agent(llm_gateway=LLMGateway(provider=_get_provider(), model=_get_model(), api_key=_get_api_key(), base_url=_get_base_url() or None), config=_ConfigShim())
            result = await sub.run("PM requested your input. Context:\n" + context[:2000] + "\n\nFocus on your role: " + role + ". Report findings back to PM.", role=role)
            await self.send({"type": "agent_response", "role": role, "role_display": role_display, "content": result or "(no output)"})
            return result or ""
        except Exception as exc:
            await self.send({"type": "agent_response", "role": role, "role_display": role_display, "content": "错误: " + str(exc)})
            return ""

    async def _run_sub_agent(self, role: str, context: str, silent: bool = False) -> str:
        """Run a sub-agent with given role and context. Returns response text."""
        from harnessgenj_dev.core.agent import Agent
        from harnessgenj_dev.llm.gateway import LLMGateway
        if not silent:
            await self.send({"type": "agent_dispatch", "role": role, "role_display": self._ROLE_DISPLAY.get(role, role), "status": "started"})
        try:
            sub = Agent(llm_gateway=LLMGateway(provider=_get_provider(), model=_get_model(), api_key=_get_api_key(), base_url=_get_base_url() or None), config=_ConfigShim())
            task = "项目经理请你分析以下内容，请用中文回答：\n\n" + context[:2000] + "\n\n你是谁：" + self._ROLE_DISPLAY.get(role, role) + "\n请从你的专业角度分析，用中文回复。"
            result = await sub.run(task, role=role)
            if not silent:
                await self.send({"type": "agent_response", "role": role, "role_display": self._ROLE_DISPLAY.get(role, role), "content": result or "(无输出)"})
            return result or ""
        except Exception as exc:
            if not silent:
                await self.send({"type": "agent_response", "role": role, "role_display": self._ROLE_DISPLAY.get(role, role), "content": "错误：" + str(exc)})
            return ""

    async def run_develop(self, content: str) -> str | None:
        agent = self._ensure_agent()
        session = self._get_session()
        if not session.messages:
            system_prompt = self._build_system_prompt(self.role)
            session.messages = [{"role": "system", "content": system_prompt}]
        session.messages.append({"role": "user", "content": content})
        agent.state.conversation_history = list(session.messages)
        await self._send_status("running")
        accumulated = ""
        try:
            # Immediate feedback so user knows agent is working
            await self.send({"type": "text_chunk", "content": "⏳ 正在分析...\n", "role": self.role})
            # Reduce max iterations for initial response (orchestrator dispatches for deep analysis)
            agent.state.max_iterations = min(agent.state.max_iterations, 5)
            result = await agent.run(content, role=self.role)
            accumulated = result or ""
            if accumulated:
                session.messages.append({"role": "assistant", "content": accumulated})
                await self.send({"type": "text_chunk", "content": accumulated, "role": self.role})
            if not self._interrupted:
                await self.send({"type": "final_answer", "content": accumulated, "iterations": agent.state.iteration_count, "role": self.role})

            # 多轮审查工作流：每轮全员评估 → 不满意回退 → 全部通过才输出
            if self.role == "project_manager" and accumulated and not self._interrupted:
                from ..llm.gateway import LLMGateway
                import re
                gw = LLMGateway(provider=_get_provider(), model=_get_model(), api_key=_get_api_key(), base_url=_get_base_url() or None)
                TEAM = ["architect", "developer", "code_reviewer", "bug_hunter", "doc_writer"]
                results = {}
                base_context = "## 用户请求\n" + content + "\n\n## 项目经理分析\n" + accumulated[:2000]
                max_passes = 3

                for pn in range(1, max_passes + 1):
                    if self._interrupted: break
                    needs_redo = set()
                    round_context = base_context

                    await self.send({"type": "agent_response", "role": "project_manager", "role_display": "项目经理", "content": "## 第 " + str(pn) + " 轮讨论开始"})

                    # 按顺序调度 A→B→C→D
                    for role in TEAM:
                        if self._interrupted: break
                        # 跳过不需要重做的Agent（除了第一轮）
                        if pn > 1 and role not in needs_redo and role in results:
                            continue

                        role_display = self._ROLE_DISPLAY.get(role, role)

                        # PM intro
                        intro_prompt = "你是项目经理。第" + str(pn) + "轮。请用中文一句话说明为什么现在要调度" + role_display + "。如果有前面角色的建议，请一并说明。"
                        intro_resp = await gw.chat(messages=[{"role": "user", "content": intro_prompt}], model=_get_model())
                        await self.send({"type": "agent_response", "role": "project_manager", "role_display": "项目经理", "content": intro_resp.content or ("调度" + role_display + "...")})

                        # 构建上下文：基础内容 + 所有之前的Agent输出
                        ctx = round_context
                        for r in TEAM:
                            if r in results:
                                ctx += "\n\n## " + self._ROLE_DISPLAY.get(r, r) + " (最近)\n" + results.get(r, "")[:1500]

                        # Run agent
                        agent_output = await self._run_sub_agent(role, ctx, silent=False)
                        results[role] = agent_output
                        round_context += "\n\n## " + role_display + " 输出\n" + agent_output[:2000]

                    # 轮次结束：PM 检查是否需要回退
                    if self._interrupted: break
                    review_prompt = "你是项目经理。第" + str(pn) + "轮已完成。\n"
                    for r in TEAM:
                        if r in results:
                            review_prompt += "### " + self._ROLE_DISPLAY.get(r, r) + "\n" + results.get(r, "")[:800] + "\n\n"
                    review_prompt += "请判断：\n1. 是否有任何角色对前序角色的工作不满意？（如B认为A需要修改）\n2. 是否需要回退到某个角色重新执行？\n\n"
                    review_prompt += "回复格式：\n- 如果全部通过：回复 PASS\n- 如果需要回退：回复 REDO:角色名 (如 REDO:architect)\n- 只用一行回复，不要解释"

                    review_resp = await gw.chat(messages=[{"role": "user", "content": review_prompt}], model=_get_model())
                    decision = (review_resp.content or "PASS").strip().upper()

                    if "REDO:" in decision:
                        # Extract role to redo
                        redos = re.findall(r'REDO:(\w+)', decision)
                        for rd in redos:
                            if rd in TEAM:
                                needs_redo.add(rd)
                        if needs_redo:
                            redo_names = ", ".join(self._ROLE_DISPLAY.get(r, r) for r in needs_redo)
                            await self.send({"type": "agent_response", "role": "project_manager", "role_display": "项目经理", "content": "## 需要回退优化\n" + redo_names + " 需要重新执行。第" + str(pn + 1) + "轮将聚焦这些角色。"})
                            base_context = round_context  # pass full context to next round
                            continue
                    # PASS or no clear redo → complete
                    break

                # PM final summary (mandatory)
                raw = ""
                for r in TEAM:
                    if r in results:
                        raw += "### " + self._ROLE_DISPLAY.get(r, r) + "\n" + results.get(r, "")[:1000] + "\n\n"
                        session.messages.append({"role": "assistant", "content": "[" + self._ROLE_DISPLAY.get(r, r) + "]: " + results.get(r, "")[:500]})
                final_prompt = "你是项目经理。团队" + str(pn) + "轮讨论已完成。\n用户请求：\n" + content[:1000] + "\n\n## 团队结论\n" + raw + "\n请给用户最终回复：总结讨论过程、关键决策、下一步行动。用中文，简洁专业。"
                sr = await gw.chat(messages=[{"role": "user", "content": final_prompt}], model=_get_model())
                final_summary = sr.content or "团队分析完成。"
                session.messages.append({"role": "assistant", "content": "[PJM Final]: " + final_summary[:1000]})
                await self.send({"type": "agent_response", "role": "project_manager", "role_display": "项目经理", "content": final_summary})

            return accumulated
        except asyncio.CancelledError:
            if accumulated:
                session.messages.append({"role": "assistant", "content": accumulated})
                await self.send({"type": "final_answer", "content": accumulated + "\n[已取消]", "role": self.role})
            raise
        except Exception as exc:
            await self.send({"type": "error", "message": str(exc)})
            return None
        finally:
            await self._send_status("idle")
            self._interrupted = False

    _ROLE_DISPLAY = {
        "project_manager": "项目经理",
        "product_manager": "产品经理",
        "architect": "架构师",
        "developer": "开发者",
        "code_reviewer": "代码审查员",
        "bug_hunter": "Bug猎人",
        "doc_writer": "文档编写者",
    }

        
    async def _dispatch_mentions(self, pm_text: str, user_request: str) -> str:
        """PM dispatches @mentioned agents, collects results, synthesizes summary.
        Only PM dispatches; agents report findings back to PM.
        """
        import re
        from harnessgenj_dev.core.agent import Agent
        from harnessgenj_dev.llm.gateway import LLMGateway

        mentions = re.findall(r'@(architect|developer|code_reviewer|bug_hunter|doc_writer)', pm_text)
        if not mentions:
            return ""

        seen = set()
        agent_results = {}
        for role in mentions:
            if role in seen:
                continue
            seen.add(role)

            role_display = self._ROLE_DISPLAY.get(role, role)
            await self.send({"type": "agent_dispatch", "role": role, "role_display": role_display, "status": "started"})

            try:
                sub_agent = Agent(
                    llm_gateway=LLMGateway(provider=_get_provider(), model=_get_model(), api_key=_get_api_key(), base_url=_get_base_url() or None),
                    config=_ConfigShim(),
                )
                ctx_parts = [
                    "## User Original Request\n" + user_request[:1500],
                    "## Product Manager Analysis\n" + pm_text[:2000],
                ]
                if agent_results:
                    prev = "\n".join("[" + r + "] " + agent_results[r][:800] for r in agent_results)
                    ctx_parts.append("## Previous Agent Findings\n" + prev)

                task_prompt = (
                    "You are the " + role_display + ". PM needs your expertise.\n\n"
                    "Complete your part based on the context. Focus ONLY on your role.\n"
                    "Do NOT assign tasks to other agents. Report back to PM.\n\n"
                    + "\n".join(ctx_parts)
                )
                sub_result = await sub_agent.run(task_prompt, role=role)
                agent_results[role] = sub_result
                await self.send({"type": "agent_response", "role": role, "role_display": role_display, "content": sub_result})
            except Exception as exc:
                await self.send({"type": "agent_response", "role": role, "role_display": role_display, "content": "\u9519\u8bef: " + str(exc)})
                agent_results[role] = "(error)"

        if not agent_results:
            return ""

                # PM ALWAYS synthesizes final summary (mandatory step)
        await self.send({"type": "agent_dispatch", "role": "product_manager", "role_display": "产品经理", "status": "started"})
        try:
            from ..llm.gateway import LLMGateway
            gw = LLMGateway(provider=_get_provider(), model=_get_model(), api_key=_get_api_key(), base_url=_get_base_url() or None)
            rlines = []
            for r in agent_results:
                rlines.append("### " + self._ROLE_DISPLAY.get(r, r) + " | " + agent_results[r][:1500])
            body = "## Project Update\n## User Request\n" + user_request[:1000]
            if rlines:
                body += "\n\n" + chr(10).join(rlines)
            body += "\n\nSummarize what was accomplished, key outcomes, next steps."
            resp = await gw.chat(messages=[{"role": "user", "content": body}], model=_get_model())
            return resp.content or "Team work complete."
        except Exception:
            fb = "## 团队工作完成\n\n"
            for r in agent_results:
                fb += "- **" + self._ROLE_DISPLAY.get(r, r) + "**: 已完成\n"
            return fb

    async def run_develop_oneshot(self, content: str) -> dict[str, Any]:
        from harnessgenj_dev.core.agent import Agent
        from harnessgenj_dev.llm.gateway import LLMGateway
        from harnessgenj_dev.tools.registry import auto_register
        auto_register()
        agent = Agent(llm_gateway=LLMGateway(
            provider=_get_provider(), model=_get_model(),
            api_key=_get_api_key(), base_url=_get_base_url() or None,
        ), config=_ConfigShim())
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
    await session.send({"type": "session_switched", "session_id": session._session_id, "messages": session.conversation_history})

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "develop":
                content = data.get("content", "")
                role = data.get("role", "developer")
                if role:
                    session.role = role
                if content:
                    # Don't await task — let message loop stay responsive
                    async def _run_and_save():
                        try:
                            await session.run_develop(content)
                        except asyncio.CancelledError:
                            pass
                        except Exception:
                            pass
                        finally:
                            session.save_session()  # final save at end
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
                    await session.send({"type": "session_switched", "session_id": sid, "messages": session.conversation_history, "role": session.role})
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
    except Exception:
        pass
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
            provider=provider, model=model,
            api_key=api_key, base_url=base_url or None,
            max_retries=0,
        )
        response = await gateway.chat(
            messages=[{"role": "user", "content": "Say OK in one word."}]
        )
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
    if _file_root_set and not Path(path).is_absolute():
        resolved = (_file_root / path).resolve()
    else:
        resolved = Path(path).resolve()
    if not resolved.exists():
        raise HTTPException(404, "Path not found")
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
                entries.append({
                    "name": child.name,
                    "path": str(child),
                    "is_dir": child.is_dir(),
                    "size": child.stat().st_size,
                    "modified": int(child.stat().st_mtime),
                })
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
    external = body.get("is_external", False)
    if not name:
        raise HTTPException(400, "name is required")
    if external and path:
        add_external_project(name, path, description)
    elif path:
        add_project(name, path, description)
    else:
        # No path = auto-create under workspace
        add_project(name, description=description)
    return {"status": "added", "name": name}


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
async def api_create_session(body: dict[str, str], project: str = "default"):
    role = body.get("role", "developer")
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
