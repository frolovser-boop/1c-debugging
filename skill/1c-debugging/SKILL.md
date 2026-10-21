---
name: 1c-debugging
description: "Используй при отладке 1С без Конфигуратора через MCP."
---

# Отладка 1С без Конфигуратора

Класс задач: поставить точку останова, поймать останов, разобрать стек/переменные/вычислить BSL-выражение в работающей сессии 1С — не открывая Конфигуратор. Механизм: расширение VS Code/Cursor «1C Dev Tools» (whiterabbit.1c-dev-tools) поднимает MCP-сервер отладки; агент ходит в него как MCP-клиент по streamable HTTP.

## Стоящие правила

- Первым вызывай `onec_debug_status` — он отвечает, есть ли сессия `type=onec`, какие launchConfigs и где файл снимка. Не ставь брейкпойнты и не стартуй отладку до статуса.
- Порт 18791 живёт только в процессе редактора с активным расширением. Если он закрыт — попроси пользователя открыть проект 1С в VS Code/Cursor; сам редактор не запускай и порт не жди вечно.
- `onec_debug_start` требует `launch.json` (`type: "onec"`) в окне редактора. При `hasOnecSession=false` собери launch.json по схеме из `references/onec-debug-mcp.md` (известные ключи только из readme VSIX, не придумывай) и попроси пользователя начать отладку в том же окне, где активен MCP-сервер.
- Действия в клиенте 1С (кнопка, проведение документа) из чата не нажимаются. Полный автоматический цикл = сессия отладки через MCP + прогон сценария веб-клиентом (скилл web-test); иначе остановы триггерит пользователь.
- Отладка расширения работает только по HTTP-протоколу отладки платформы — обычный (не-HTTP) режим отладки этим путём не подключить.

## Подключение

1. Живость: `netstat -ano | grep 18791` — `LISTENING` значит редактор с расширением открыт.
2. Дальше скриптом `scripts/onec_debug_mcp.py` (сам делает handshake с Mcp-Session-Id и парсит SSE):
   - `python scripts/onec_debug_mcp.py status` — статус сессии;
   - `python scripts/onec_debug_mcp.py list` — список инструментов;
   - `python scripts/onec_debug_mcp.py call onec_debug_set_breakpoint '{"path":"...bsl","line":123}'`.
3. Ручной вариант (если скрипт недоступен): POST initialize (protocolVersion 2025-03-26, Accept: application/json + text/event-stream) → взять заголовок `Mcp-Session-Id` из ответа и класть в каждый следующий запрос → notifications/initialized → tools/list → tools/call. Ответ может быть SSE-фреймом — парси строки `data:`.

## Инструменты (11)

`onec_debug_status` · `start` · `stop` · `set_breakpoint` (path к .bsl + line) · `stack` · `variables` · `evaluate` (BSL-выражение в текущем кадре, как Watch) · `step_into` / `step_over` / `step_out` · `continue`. Полная карта с параметрами — `references/onec-debug-mcp.md`.

Каждый останов пишет снимок стека в `%TEMP%\1c-dev-tools-debug-snapshot.json` — читается из любой сессии на той же машине.

## Альтернатива без расширения

`dbgs.exe` из bin платформы (автономный HTTP-сервер отладки) + клиент с `/DEBUG` + RDBG-протокол по HTTP вручную. Тяжелее — расширение инкапсулирует то же самое; прямой протокол бери только если расширения нет или сервер отладки удалённый.
