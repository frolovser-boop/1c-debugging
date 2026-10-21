# -*- coding: utf-8 -*-
"""
Реализация HTTP/XML протокола отладки 1С:Предприятия (RDBG).
Работает напрямую с dbgs.exe без сторонних зависимостей (чистая стандартная библиотека Python).
"""

import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any

NS_BASE = "http://v8.1c.ru/8.3/debugger/debugBaseData"
NS_RDBG = "http://v8.1c.ru/8.3/debugger/debugRDBGRequestResponse"
NS_BP = "http://v8.1c.ru/8.3/debugger/debugBreakpoints"
NS_RTGT = "http://v8.1c.ru/8.3/debugger/dbgtgtRemoteRequestResponse"
NS_AUTOATTACH = "http://v8.1c.ru/8.3/debugger/debugAutoAttach"

# Стандартный PropertyID для модуля управляемого приложения
DEFAULT_MODULE_PROP_ID = "d22e852a-cf8a-4f77-8ccb-3548e7792bea"


def _esc(s: Any) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _strip_ns(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


class RdbgClient:
    """Клиент протокола RDBG для взаимодействия с сервером отладки dbgs.exe."""

    def __init__(self, host: str = "127.0.0.1", port: int = 1572, timeout: int = 10):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}/e1crdbg"

    def post(self, cmd: str, body: str, path: str = "rdbg", dbgui: Optional[str] = None, timeout: Optional[int] = None) -> Tuple[int, str]:
        """Отправляет POST-запрос с телом XML в кодировке windows-1251 на указанный ресурс RDBG."""
        url = f"{self.base_url}/{path}?cmd={cmd}"
        if dbgui:
            url += f"&dbgui={dbgui}"

        data = body.encode("windows-1251", errors="replace")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "User-Agent": "1CV8",
                "Content-Type": "application/xml; charset=windows-1251",
            },
            method="POST"
        )
        t = timeout or self.timeout
        try:
            with urllib.request.urlopen(req, timeout=t) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                return resp.status, text
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", errors="replace")
            return e.code, text
        except Exception as e:
            return 0, f"NETWORK_ERROR: {str(e)}"

    # --- Команды интерфейса отладчика (UI) ---

    def attach_debug_ui(self, alias: str, ui_id: str) -> Tuple[int, str]:
        """Регистрирует UI отладчика в dbgs."""
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<request xmlns="{NS_RDBG}">
  <infoBaseAlias>{_esc(alias)}</infoBaseAlias>
  <idOfDebuggerUI>{_esc(ui_id)}</idOfDebuggerUI>
</request>"""
        return self.post("attachDebugUI", body, path="rdbg", dbgui=ui_id)

    def init_settings(self, alias: str, ui_id: str) -> Tuple[int, str]:
        """Инициализирует настройки сессии UI."""
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<request xmlns="{NS_RDBG}">
  <infoBaseAlias>{_esc(alias)}</infoBaseAlias>
  <idOfDebuggerUI>{_esc(ui_id)}</idOfDebuggerUI>
</request>"""
        return self.post("initSettings", body, path="rdbg", dbgui=ui_id)

    def set_auto_attach_settings(self, alias: str, ui_id: str, types: Optional[List[str]] = None) -> Tuple[int, str]:
        """Устанавливает типы процессов для автоматического подключения."""
        if not types:
            types = ["Client", "ManagedClient", "Server", "ServerEmulation"]
        
        type_tags = "".join(f'<targetType xmlns="{NS_AUTOATTACH}">{_esc(t)}</targetType>' for t in types)
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<request xmlns="{NS_RDBG}">
  <infoBaseAlias>{_esc(alias)}</infoBaseAlias>
  <idOfDebuggerUI>{_esc(ui_id)}</idOfDebuggerUI>
  <autoAttachSettings xmlns="{NS_RDBG}">{type_tags}</autoAttachSettings>
</request>"""
        return self.post("setAutoAttachSettings", body, path="rdbg", dbgui=ui_id)

    def set_breakpoints(self, alias: str, ui_id: str, bps: List[Dict[str, Any]]) -> Tuple[int, str]:
        """
        Устанавливает точки останова в формате 1С 8.3.27.
        bps: список словарей вида:
          {'object_id': str, 'property_id': str (optional), 'line': int}
        """
        module_bps = []
        for bp in bps:
            obj_id = bp.get("object_id", "")
            prop_id = bp.get("property_id") or DEFAULT_MODULE_PROP_ID
            line = bp.get("line", 1)
            module_bps.append(f"""<debugBreakpoints:moduleBPInfo>
  <debugBreakpoints:id>
    <type>ConfigModule</type>
    <objectID>{_esc(obj_id)}</objectID>
    <propertyID>{_esc(prop_id)}</propertyID>
  </debugBreakpoints:id>
  <debugBreakpoints:bpInfo>
    <debugBreakpoints:line>{int(line)}</debugBreakpoints:line>
    <debugBreakpoints:hitCount>0</debugBreakpoints:hitCount>
  </debugBreakpoints:bpInfo>
</debugBreakpoints:moduleBPInfo>""")

        workspace = "".join(module_bps)
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<request xmlns="{NS_BASE}" xmlns:debugBreakpoints="{NS_BP}" xmlns:debugRDBGRequestResponse="{NS_RDBG}">
  <debugRDBGRequestResponse:infoBaseAlias>{_esc(alias)}</debugRDBGRequestResponse:infoBaseAlias>
  <debugRDBGRequestResponse:idOfDebuggerUI>{_esc(ui_id)}</debugRDBGRequestResponse:idOfDebuggerUI>
  <debugRDBGRequestResponse:bpWorkspace>{workspace}</debugRDBGRequestResponse:bpWorkspace>
</request>"""
        return self.post("setBreakpoints", body, path="rdbg", dbgui=ui_id)

    def get_dbg_targets(self, alias: str, ui_id: str) -> List[Dict[str, str]]:
        """Запрашивает список активных отладочных целей (сеансов/процессов 1С)."""
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<request xmlns="{NS_RDBG}">
  <infoBaseAlias>{_esc(alias)}</infoBaseAlias>
  <idOfDebuggerUI>{_esc(ui_id)}</idOfDebuggerUI>
</request>"""
        status, resp = self.post("getDbgTargets", body, path="rdbg", dbgui=ui_id)
        if status != 200 or not resp.strip():
            return []

        targets = []
        try:
            root = ET.fromstring(resp)
            # 8.3.27 target nodes
            for elem in root.iter():
                tag = _strip_ns(elem.tag)
                if tag in ("id", "targetID"):
                    tid = None
                    t_info = {}
                    # Если внутри elem есть тег id
                    for ch in elem:
                        ctag = _strip_ns(ch.tag)
                        if ctag == "id" and ch.text:
                            tid = ch.text.strip()
                        elif ch.text:
                            t_info[ctag] = ch.text.strip()
                    
                    if not tid and elem.text and re.match(r"^[0-9a-fA-F-]{36}$", elem.text.strip()):
                        tid = elem.text.strip()

                    if tid and tid not in [t["id"] for t in targets]:
                        t_info["id"] = tid
                        targets.append(t_info)
        except Exception:
            # Fallback через regex
            for tid in re.findall(r'<id>([0-9a-fA-F-]{36})</id>', resp):
                if tid not in [t["id"] for t in targets]:
                    targets.append({"id": tid})

        return targets

    def attach_detach_targets(self, alias: str, ui_id: str, attach: Optional[List[str]] = None, detach: Optional[List[str]] = None) -> Tuple[int, str]:
        """Привязывает или отвязывает конкретные цели от нашего UI."""
        attach = attach or []
        detach = detach or []

        inner = f"""<debugRDBGRequestResponse:infoBaseAlias>{_esc(alias)}</debugRDBGRequestResponse:infoBaseAlias>
<debugRDBGRequestResponse:idOfDebuggerUI>{_esc(ui_id)}</debugRDBGRequestResponse:idOfDebuggerUI>"""

        for tid in attach:
            inner += f"""<debugRDBGRequestResponse:attach>true</debugRDBGRequestResponse:attach>
<debugRDBGRequestResponse:id><id>{_esc(tid)}</id></debugRDBGRequestResponse:id>"""

        for tid in detach:
            inner += f"""<debugRDBGRequestResponse:attach>false</debugRDBGRequestResponse:attach>
<debugRDBGRequestResponse:id><id>{_esc(tid)}</id></debugRDBGRequestResponse:id>"""

        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<request xmlns="{NS_BASE}" xmlns:debugRDBGRequestResponse="{NS_RDBG}">
{inner}
</request>"""
        return self.post("attachDetachDbgTargets", body, path="rdbg", dbgui=ui_id)

    # --- Команды конкретного таргета (rtgt) ---

    def start_target(self, target_id: str) -> Tuple[int, str]:
        """Запускает сеанс отладки для конкретного таргета."""
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<request xmlns="{NS_RTGT}">
  <idOfDebuggerUI>{_esc(target_id)}</idOfDebuggerUI>
</request>"""
        return self.post("startDBGTGT", body, path="rtgt")

    def ping_target(self, target_id: str, bp_version: Optional[str] = None, seance_id: Optional[str] = None, alias: Optional[str] = None) -> Tuple[int, str]:
        """Опрашивает события отладочной цели (pingDBGTGT)."""
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<request xmlns="{NS_RTGT}">
  <idOfDebuggerUI>{_esc(target_id)}</idOfDebuggerUI>
</request>"""
        return self.post("pingDBGTGT", body, path="rtgt", timeout=12)

    def ping_ui(self, alias: str, ui_id: str) -> Tuple[int, str]:
        """Опрашивает центральные события UI отладчика (pingDebugUIParams)."""
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<request xmlns="{NS_RDBG}">
  <infoBaseAlias>{_esc(alias)}</infoBaseAlias>
  <idOfDebuggerUI>{_esc(ui_id)}</idOfDebuggerUI>
</request>"""
        return self.post("pingDebugUIParams", body, path="rdbg", dbgui=ui_id, timeout=12)

    def get_call_stack(self, alias: str, ui_id: str, target_id: str) -> Tuple[int, str]:
        """Запрашивает стек вызовов остановленной цели."""
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<request xmlns="{NS_BASE}" xmlns:debugRDBGRequestResponse="{NS_RDBG}">
  <debugRDBGRequestResponse:infoBaseAlias>{_esc(alias)}</debugRDBGRequestResponse:infoBaseAlias>
  <debugRDBGRequestResponse:idOfDebuggerUI>{_esc(ui_id)}</debugRDBGRequestResponse:idOfDebuggerUI>
  <debugRDBGRequestResponse:targetID><id>{_esc(target_id)}</id></debugRDBGRequestResponse:targetID>
</request>"""
        return self.post("getCallStack", body, path="rdbg", dbgui=ui_id)

    def step(self, alias: str, ui_id: str, target_id: str, action: str = "Continue") -> Tuple[int, str]:
        """
        Управляет выполнением:
        action: 'Continue', 'Step' (StepOver), 'StepIn', 'StepOut'
        """
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<request xmlns="{NS_BASE}" xmlns:debugRDBGRequestResponse="{NS_RDBG}">
  <debugRDBGRequestResponse:infoBaseAlias>{_esc(alias)}</debugRDBGRequestResponse:infoBaseAlias>
  <debugRDBGRequestResponse:idOfDebuggerUI>{_esc(ui_id)}</debugRDBGRequestResponse:idOfDebuggerUI>
  <debugRDBGRequestResponse:targetID><id>{_esc(target_id)}</id></debugRDBGRequestResponse:targetID>
  <debugRDBGRequestResponse:action>{_esc(action)}</debugRDBGRequestResponse:action>
</request>"""
        return self.post("step", body, path="rdbg", dbgui=ui_id)
