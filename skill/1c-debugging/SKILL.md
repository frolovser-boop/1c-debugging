---
name: 1c-debugging
description: "Универсальная отладка 1С:Предприятия без Конфигуратора: автономный Python RDBG движок и MCP-сервер для AI-агентов (Hermes, Claude Code, Cursor, Cline, Antigravity)."
---

# 1C Debugging: Отладка 1С для AI-агентов и разработчиков

Навык предоставляет два режима работы для отладки любых конфигураций 1С (файловых и серверных):

1. **Режим А: Автономный Headless RDBG (без VS Code)**
   * Использует чистый Python-пакет `onec_debug`.
   * Работает напрямую с `dbgs.exe` по протоколу RDBG (HTTP/XML).
   * Автоматически определяет установленную платформу 1С и базы из `ibases.v8i`.
   * Запускает клиента с корректным `infoBaseAlias` (`DefAlias` для файловых, имя базы для серверных).
   * Команда MCP: `python -m onec_debug mcp` (доступно 9 инструментов отладки).

2. **Режим Б: Интеграция с VS Code / Cursor (через расширение 1C Dev Tools)**
   * Расширение `whiterabbit.1c-dev-tools` поднимает локальный MCP-сервер на `http://127.0.0.1:18791/mcp`.
   * Stdio-мост: `python mcp-bridge/onec_debug_stdio.py`.

---

## Быстрый старт (CLI)

```bash
# 1. Проверка окружения платформы и поиск баз
python -m onec_debug test

# 2. Вывод списка всех баз пользователя из ibases.v8i
python -m onec_debug list

# 3. Запуск отладки конкретной базы (файловой или серверной)
python -m onec_debug run "test"
python -m onec_debug run --base "test"
python -m onec_debug run --file "C:\1C_Base\test-file"
python -m onec_debug run --conn "Srvr=\"localhost\";Ref=\"test\";"
```

---

## Подключение как MCP-сервер к AI-агентам

В файл конфигурации агента (`claude_desktop_config.json`, `cursor`, `cline`):

```json
{
  "mcpServers": {
    "1c-debug": {
      "command": "python",
      "args": ["-m", "onec_debug", "mcp"],
      "cwd": "C:/Hermes/profiles/1c-asbnu-developer-cc/skills/1c-debugging"
    }
  }
}
```

### Доступные MCP-инструменты:
* `onec_list_bases` — список всех доступных баз из списка 1С.
* `onec_start_debugging` — запуск сеанса отладки (принимает имя базы, путь к папке или строку подключения).
* `onec_set_breakpoints` — установка точек останова (object_id, line).
* `onec_get_targets` — список активных процессов/сеансов 1С.
* `onec_get_call_stack` — получение стека вызовов при останове.
* `onec_continue` — продолжить выполнение (F5).
* `onec_step_over` / `step_into` / `step_out` — пошаговое выполнение.
* `onec_stop_debugging` — завершение отладки и закрытие клиента 1С.

---

## Правила протокола RDBG (Платформа 8.3.27)

1. **Тип базы и Alias:**
   * **Файловая база:** `infoBaseAlias = "DefAlias"`. Запуск: `/F"путь"`.
   * **Серверная база:** `infoBaseAlias = "<имя базы>"` (строго совпадает с именем базы в кластере). Запуск: `/S"host:port\name"`.
2. **Параметры запуска клиента 1С:**
   * Строго HTTP: `/DEBUG -http /DEBUGGERURL "http://127.0.0.1:1572"`.
   * Суффикс `/e1crdbg` в параметре `/DEBUGGERURL` указывать **НЕЛЬЗЯ**.
3. **PropertyID модулей:**
   * Стандартный модуль управляемого приложения: `d22e852a-cf8a-4f77-8ccb-3548e7792bea`.
