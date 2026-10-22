# -*- coding: utf-8 -*-
"""
Универсальный MCP-сервер (Model Context Protocol) для отладки 1С:Предприятия.
Поддерживает два режима транспорта:
1. stdio (JSON-RPC по стандартным потокам ввода/вывода) — для локальных агентов (Cursor, Claude Code, Cline, Hermes).
2. HTTP (порт /mcp) — для Docker-контейнеров, удалённых сервисов и сетевого взаимодействия.
"""

import sys
import json
import logging
from typing import Dict, Any, Optional
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .detector import list_known_bases, resolve_base, detect_platform
from .session import DebugSession

logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

ACTIVE_SESSION: Optional[DebugSession] = None


def get_tool_definitions() -> list:
    return [
        {
            "name": "onec_list_bases",
            "description": "Возвращает список всех зарегистрированных информационных баз 1С пользователя (из ibases.v8i) с типами (файловая / серверная) и параметрами подключения.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        },
        {
            "name": "onec_start_debugging",
            "description": "Запускает автономный сеанс отладки 1С без Конфигуратора для указанной базы (по имени, пути к папке или строке подключения).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "base": {
                        "type": "string",
                        "description": "Имя базы из списка ibases.v8i, путь к каталогу файловой базы или строка соединения (например, 'test' или 'File=\"C:\\1C_Base\\test-file\"' или 'Srvr=\"localhost\";Ref=\"test\";')"
                    },
                    "user": {
                        "type": "string",
                        "description": "Имя пользователя 1С (по умолчанию 'Администратор')",
                        "default": "Администратор"
                    },
                    "password": {
                        "type": "string",
                        "description": "Пароль пользователя 1С (если есть)",
                        "default": ""
                    },
                    "thick_client": {
                        "type": "boolean",
                        "description": "Запускать толстый клиент (1cv8.exe) вместо тонкого (1cv8c.exe)",
                        "default": False
                    }
                },
                "required": ["base"],
                "additionalProperties": False
            }
        },
        {
            "name": "onec_set_breakpoints",
            "description": "Устанавливает точки останова в конфигурации 1С.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "breakpoints": {
                        "type": "array",
                        "description": "Список точек останова",
                        "items": {
                            "type": "object",
                            "properties": {
                                "object_id": {
                                    "type": "string",
                                    "description": "UUID модуля или объекта метаданных"
                                },
                                "line": {
                                    "type": "integer",
                                    "description": "Номер строки (начиная с 1)"
                                },
                                "property_id": {
                                    "type": "string",
                                    "description": "PropertyID модуля (по умолчанию стандартный модуль управляемого приложения)"
                                }
                            },
                            "required": ["object_id", "line"]
                        }
                    }
                },
                "required": ["breakpoints"],
                "additionalProperties": False
            }
        },
        {
            "name": "onec_get_targets",
            "description": "Возвращает список активных отладочных целей (сеансов/процессов 1С).",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        },
        {
            "name": "onec_get_call_stack",
            "description": "Возвращает стек вызовов остановленного сеанса 1С.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        },
        {
            "name": "onec_continue",
            "description": "Продолжает выполнение остановленного сеанса 1С (F5 / Continue).",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        },
        {
            "name": "onec_step_over",
            "description": "Выполняет шаг через текущую строку (F10 / StepOver).",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        },
        {
            "name": "onec_step_into",
            "description": "Выполняет шаг с заходом в процедуру/функцию (F11 / StepInto).",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        },
        {
            "name": "onec_step_out",
            "description": "Выполняет шаг выхода из текущей процедуры/функции (Shift+F11 / StepOut).",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        },
        {
            "name": "onec_stop_debugging",
            "description": "Останавливает активный сеанс отладки 1С и завершает процесс клиента.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
    ]


def handle_tool_call(name: str, arguments: Dict[str, Any]) -> Any:
    global ACTIVE_SESSION

    if name == "onec_list_bases":
        bases = list_known_bases()
        items = []
        for b in bases:
            items.append({
                "name": b.name,
                "type": "file" if b.is_file else "server",
                "connect": b.connect_str,
                "alias": b.alias,
                "launch_arg": b.launch_arg
            })
        return {"bases": items, "count": len(items)}

    elif name == "onec_start_debugging":
        if ACTIVE_SESSION and ACTIVE_SESSION.is_active:
            ACTIVE_SESSION.stop()

        base_id = arguments["base"]
        user = arguments.get("user", "Администратор")
        password = arguments.get("password", "")
        thick = arguments.get("thick_client", False)

        base_info = resolve_base(base_id)
        session = DebugSession(
            base=base_info,
            user=user,
            password=password,
            thick_client=thick
        )
        session.start()
        target_id = session.wait_for_target(timeout_sec=15)
        ACTIVE_SESSION = session

        return {
            "status": "started",
            "base": base_info.name,
            "type": "file" if base_info.is_file else "server",
            "alias": base_info.alias,
            "target_id": target_id or "waiting_for_connection",
            "message": f"Сеанс отладки для базы '{base_info.name}' запущен."
        }

    elif name == "onec_set_breakpoints":
        if not ACTIVE_SESSION or not ACTIVE_SESSION.is_active:
            return {"error": "Нет активного сеанса отладки. Сначала вызовите onec_start_debugging."}
        bps = arguments.get("breakpoints", [])
        status, resp = ACTIVE_SESSION.set_breakpoints(bps)
        return {"status": "ok" if status == 200 else "error", "http_status": status, "response": resp[:300]}

    elif name == "onec_get_targets":
        if not ACTIVE_SESSION or not ACTIVE_SESSION.is_active:
            return {"error": "Нет активного сеанса отладки."}
        targets = ACTIVE_SESSION.client.get_dbg_targets(ACTIVE_SESSION.base.alias, ACTIVE_SESSION.ui_id)
        return {"targets": targets, "active_target_id": ACTIVE_SESSION.active_target_id}

    elif name == "onec_get_call_stack":
        if not ACTIVE_SESSION or not ACTIVE_SESSION.is_active:
            return {"error": "Нет активного сеанса отладки."}
        status, resp = ACTIVE_SESSION.get_stack()
        return {"status": status, "stack": resp}

    elif name == "onec_continue":
        if not ACTIVE_SESSION or not ACTIVE_SESSION.is_active:
            return {"error": "Нет активного сеанса отладки."}
        status, resp = ACTIVE_SESSION.continue_execution()
        return {"status": status, "response": resp[:200]}

    elif name == "onec_step_over":
        if not ACTIVE_SESSION or not ACTIVE_SESSION.is_active:
            return {"error": "Нет активного сеанса отладки."}
        status, resp = ACTIVE_SESSION.step_over()
        return {"status": status, "response": resp[:200]}

    elif name == "onec_step_into":
        if not ACTIVE_SESSION or not ACTIVE_SESSION.is_active:
            return {"error": "Нет активного сеанса отладки."}
        status, resp = ACTIVE_SESSION.step_into()
        return {"status": status, "response": resp[:200]}

    elif name == "onec_step_out":
        if not ACTIVE_SESSION or not ACTIVE_SESSION.is_active:
            return {"error": "Нет активного сеанса отладки."}
        status, resp = ACTIVE_SESSION.step_out()
        return {"status": status, "response": resp[:200]}

    elif name == "onec_stop_debugging":
        if ACTIVE_SESSION:
            ACTIVE_SESSION.stop()
            ACTIVE_SESSION = None
            return {"status": "stopped", "message": "Сеанс отладки успешно завершён."}
        return {"status": "idle", "message": "Активный сеанс не был запущен."}

    else:
        raise ValueError(f"Неизвестный инструмент: {name}")


def process_jsonrpc_request(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Обрабатывает входящее сообщение протокола MCP / JSON-RPC."""
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "1c-debug",
                    "version": "1.0.0"
                }
            }
        }
    elif method == "notifications/initialized":
        return None
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": get_tool_definitions()
            }
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        try:
            res = handle_tool_call(tool_name, tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(res, ensure_ascii=False, indent=2)
                        }
                    ]
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "isError": True,
                    "content": [
                        {
                            "type": "text",
                            "text": f"Ошибка выполнения {tool_name}: {str(e)}"
                        }
                    ]
                }
            }
    elif req_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Метод не найден: {method}"
            }
        }
    return None


def run_stdio_mcp_server():
    """Основной цикл обработки JSON-RPC MCP протокола через stdio."""
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except Exception:
            continue

        resp = process_jsonrpc_request(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


class McpHttpHandler(BaseHTTPRequestHandler):
    """HTTP обработчик для сетевого/Docker MCP взаимодействия."""

    def do_POST(self):
        ln = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(ln).decode("utf-8", errors="replace") if ln else ""
        try:
            req = json.loads(body)
            resp = process_jsonrpc_request(req) or {}
            out = json.dumps(resp, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
        except Exception as e:
            err = json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": str(e)}}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)

    def do_GET(self):
        if self.path in ("/", "/health"):
            data = b'{"status": "ok", "service": "1c-debug-mcp"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


def run_http_mcp_server(host: str = "0.0.0.0", port: int = 8080):
    """Запускает HTTP MCP сервер (для Docker / удалённых агентов)."""
    server = ThreadingHTTPServer((host, port), McpHttpHandler)
    print(f"onec-debug MCP HTTP server listening on http://{host}:{port}/mcp", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("MCP HTTP server stopped.", file=sys.stderr)
