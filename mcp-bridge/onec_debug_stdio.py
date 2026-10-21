#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stdio MCP bridge to the 1C Dev Tools debug MCP server.

Bridges a stdio MCP client (Claude Code, Cursor, Cline, any MCP host) to the
Streamable-HTTP MCP server the "1C Dev Tools" VS Code/Cursor extension exposes
on http://127.0.0.1:18791/mcp while the editor is open.

Config example (Claude Code):
  claude mcp add 1c-debug -- python /path/to/onec_debug_stdio.py
Config example (Cursor / Cline, mcpServers JSON):
  {"1c-debug": {"command": "python", "args": ["/path/to/onec_debug_stdio.py"]}}

Stdlib only. Line-delimited JSON-RPC on stdin -> responses on stdout.
"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:18791/mcp"
HDRS = {"Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"}
SESSION = {"id": None}


def _post(payload, timeout=60):
    headers = dict(HDRS)
    if SESSION["id"]:
        headers["Mcp-Session-Id"] = SESSION["id"]
    req = urllib.request.Request(
        BASE, json.dumps(payload).encode("utf-8"), headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        SESSION["id"] = resp.headers.get("Mcp-Session-Id") or SESSION["id"]
        body = resp.read().decode("utf-8")
    for line in body.splitlines():
        if line.startswith("data:"):
            body = line[5:].strip()
            break
    try:
        return json.loads(body)
    except ValueError:
        return None  # 202 accepted, no body (notifications)


def main():
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except ValueError:
            continue
        if msg.get("method") == "initialize":
            SESSION["id"] = None  # fresh handshake per stdio connection
        try:
            resp = _post(msg)
        except Exception as exc:  # editor closed / port dead
            err = {"jsonrpc": "2.0", "id": msg.get("id"),
                   "error": {"code": -32000, "message": str(exc)}}
            if msg.get("id") is not None:
                sys.stdout.write(json.dumps(err, ensure_ascii=False) + "\n")
                sys.stdout.flush()
            continue
        if resp is not None and msg.get("id") is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
