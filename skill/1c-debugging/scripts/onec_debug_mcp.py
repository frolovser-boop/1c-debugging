#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Probe / call the 1C Dev Tools debug MCP server (http://127.0.0.1:18791/mcp).

The server lives in the VS Code / Cursor process with the extension active;
its port is closed when the editor is not running.

Usage:
  python onec_debug_mcp.py status            # handshake + onec_debug_status
  python onec_debug_mcp.py list              # handshake + tools/list
  python onec_debug_mcp.py call <tool> [json-args]

Streamable HTTP sequence: initialize (capture Mcp-Session-Id) ->
notifications/initialized -> tools/list | tools/call. Responses may be
SSE-framed ("data:" lines) - parsed here.
"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:18791/mcp"
HDRS = {"Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"}


def _post(payload, session_id=None, timeout=15):
    headers = dict(HDRS)
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(
        BASE, json.dumps(payload).encode("utf-8"), headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        sid = resp.headers.get("Mcp-Session-Id") or session_id
        body = resp.read().decode("utf-8")
    return sid, body


def _parse(body):
    for line in body.splitlines():
        if line.startswith("data:"):
            body = line[5:].strip()
            break
    try:
        return json.loads(body)
    except ValueError:
        return {"raw": body[:500]}


def connect():
    sid, body = _post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                       "params": {"protocolVersion": "2025-03-26",
                                  "capabilities": {},
                                  "clientInfo": {"name": "hermes-agent",
                                                 "version": "1.0"}}})
    if not sid:
        raise SystemExit("MCP server returned no Mcp-Session-Id - "
                         "is 127.0.0.1:18791 the 1c-debug server?")
    info = _parse(body).get("result", {}).get("serverInfo", {})
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    return sid, info


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "call" and len(argv) < 3:
        print("usage: onec_debug_mcp.py call <tool> [json-args]")
        return 1
    sid, info = connect()
    if cmd == "list":
        result = _parse(_post({"jsonrpc": "2.0", "id": 2,
                               "method": "tools/list"}, sid)[1])
        for tool in result.get("result", {}).get("tools", []):
            desc = (tool.get("description") or "").splitlines()[0]
            print("- %s -- %s" % (tool["name"], desc))
        return 0
    if cmd in ("status", "call"):
        name = "onec_debug_status" if cmd == "status" else argv[2]
        args = json.loads(argv[3]) if cmd == "call" and len(argv) > 3 else {}
        result = _parse(_post({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                               "params": {"name": name, "arguments": args}},
                              sid)[1])
        if "error" in result:
            print(json.dumps(result["error"], ensure_ascii=False, indent=2))
            return 2
        for item in result.get("result", {}).get("content", []):
            if item.get("type") == "text":
                print(item["text"])
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
