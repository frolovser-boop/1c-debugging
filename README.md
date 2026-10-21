# 1C Debugging — отладка 1С для ИИ-агентов (без Конфигуратора)

Готовое решение: ИИ-агент (Hermes, Claude Code, Cursor, Cline и любой MCP-хост)
ставит точки останова, ловит остановы, читает стек/переменные, вычисляет BSL-выражения
и шагает по коду 1С — без участия Конфигуратора.

## Архитектура

```
ИИ-агент ──► [вариант A: скилл Hermes]  ─┐
        └──► [вариант B/C: stdio-мост]  ─┴──► MCP "1c-debug" (расширение в редакторе)
                                                  │ RDBG по HTTP
                                                  v
                                          dbgs.exe (сервер отладки платформы)
                                                  ^ /DEBUG /DEBUGGERURL
                                            клиент 1С (1cv8c.exe)
```

- Расширение **1C Dev Tools** (`whiterabbit.1c-dev-tools`) в VS Code/Cursor поднимает
  MCP-сервер отладки на `http://127.0.0.1:18791/mcp`, пока редактор открыт.
- Адаптер расширения сам запускает `dbgs.exe` и клиент `1cv8c.exe` напрямую
  (без oscript/vrunner).
- 11 инструментов MCP: `status`, `start`, `stop`, `set_breakpoint`, `stack`,
  `variables`, `evaluate`, `step_into`, `step_over`, `step_out`, `continue`.

## Состав репозитория

| Путь | Что это |
|---|---|
| `extension/whiterabbit.1c-dev-tools-2.10.11.vsix` | Расширение с MCP-сервером отладки (MIT, © Andrew Ponomarev) |
| `extension/LICENSE.txt` | Оригинальная лицензия расширения — сохранена |
| `skill/1c-debugging/` | Скилл для Hermes Agent: SKILL.md + карта инструментов + скрипт-клиент |
| `mcp-bridge/onec_debug_stdio.py` | stdio-MCP-мост для Claude Code / Cursor / Cline / любого MCP-хоста |

## Что устанавливать (важно)

| Компонент | Нужен? | Зачем |
|---|---|---|
| Платформа 1С 8.3.x | **да** | `dbgs.exe`, `1cv8c.exe` уже внутри |
| VS Code или Cursor | **да** | в нём живёт MCP-сервер расширения |
| Расширение 1C Dev Tools | **да** | сам MCP-сервер + адаптер |
| Конфигуратор в режиме отладки **HTTP** | **да** | TCP-сессии адаптер не видит |
| OneScript (oscript/vrunner/opm) | **НЕТ для отладки** | только для команд сборки/разбора палитры (dumpToSrc, build, decompile…) |
| Серверная база 1С (Srvr="…", Ref="…") | **да** | см. «Серверная база» ниже — `/S` + `alias` = имя базы |
| Python 3.7+ | для вариантов B/C | мост — стандартная библиотека |

## Установка расширения и Конфигуратора (для всех вариантов)

```
git clone https://github.com/frolovser-boop/1c-debugging.git
code --install-extension 1c-debugging/extension/whiterabbit.1c-dev-tools-2.10.11.vsix
```
Затем в Конфигураторе: Сервис → Параметры → Отладка → протокол **HTTP**.

## Вариант A — Hermes Agent (скилл)

Скопировать `skill/1c-debugging` в профиль:
```
C:\Hermes\profiles\<имя-профиля>\skills\1c-debugging
```
Скилл подхватывается автоматически: попроси агента «отладь … без Конфигуратора».
Скрипт-клиент: `scripts/onec_debug_mcp.py` (`status` / `list` / `call <tool> '{json}'`).

## Вариант B — Claude Code (нативный MCP)

```
claude mcp add 1c-debug -- python <путь>/mcp-bridge/onec_debug_stdio.py
```

## Вариант C — Cursor / Cline / любой MCP-хост (stdio)

```json
{"mcpServers": {
  "1c-debug": {"command": "python", "args": ["<путь>/mcp-bridge/onec_debug_stdio.py"]}
}}
```
Мост прозрачен: initialize/tools/list/tools/call проходят насквозь (проверено).

## launch.json в проекте 1С (`.vscode/launch.json`)

```json
{
  "configurations": [
    {
      "type": "onec",
      "request": "launch",
      "name": "1C: Отладка",
      "debugServerHost": "localhost",
      "debugServerPort": 1560,
      "infoBaseAlias": "DefAlias",
      "autoAttachTypes": ["Client", "Server", "Job"]
    }
  ]
}
```

- `request: "attach"` — присоединиться к уже запущенному клиенту.
- `autoAttachTypes` (RDBG): `Client`, `ManagedClient`, `WebClient`, `ComConnector`,
  `Server`, `ServerEmulation`, `WebService`, `HttpService`, `OData`, `Job`,
  `JobFileMode` + мобильные; пресеты `Client`/`Server` разворачиваются в подтипы.
- Отладка расширений конфигурации: добавить `rootProject` — каталог выгрузки
  (основная конфигурация: каталог с `src/cf`; расширение: `src/cfe/<ИмяРасширения>`).

## Типовой цикл

1. `onec_debug_status` — всегда первый вызов (есть ли сессия `type=onec`).
2. Сессии нет → настроить launch.json → пользователь запускает отладку в редакторе (F5).
3. `set_breakpoint` (`path` к .bsl + `line`) → `start` → останов.
4. Разбор: `stack`, `variables`, `evaluate` (BSL-выражение в кадре, как Watch).
5. Маневры: `step_into` / `step_over` / `step_out` / `continue` / `stop`.

Каждый останов пишет снимок стека в `%TEMP%\1c-dev-tools-debug-snapshot.json`.

## Ограничения

- Действия в клиенте 1С (кнопки, проведение) агент не нажимает: человек,
  либо веб-клиент + прогон Тестировщиком.
- Один клиент = один сервер отладки; Конфигуратор и агент не цепляются одновременно.
- Порт 18791 живёт только в открытом редакторе с активным расширением.
- `infoBaseAlias`/пути — адаптируются под базу на месте (2 минуты).

## Серверная база (Srvr="…", Ref="…")

Серверная база запускается ключом `/S` — **не** `/F` (файловая база) и **не** `/IBName` (не работает):

```
1cv8c.exe ENTERPRISE /S"localhost:1541\\scenario" /N"Администратор" /DEBUG -http /DEBUGGERURL "http://127.0.0.1:1572" /O Normal
```

Критично:

- **`infoBaseAlias` = имя базы** (`scenario`), а не `DefAlias`. С `DefAlias` getDbgTargets возвращает 0 целей (тихий отказ). Работает перебор: `scenario` / `SCENARIO` / `Scenario` — все сработают.
- **Протокол отладки обязан совпадать**: если база настроена на HTTP — только `/DEBUG -http /DEBUGGERURL "http://..."`. TCP-флаги (`/DebugServer`, `/DebugServerPort`) дают ошибку «Неверно указан протокол отладки: на сервере - "http", в запускаемом приложении - "tcp"».
- `/DEBUGGERURL` = `http://host:port` БЕЗ `/e1crdbg`. Клиент достраивает путь сам — с суффиксом цели не регистрируются.
- Запуск через расширенный конфигуратор: `1cv8.exe DESIGNER /S"host:port\база" /N"Администратор" /DumpCfg "cfg.cf"` — выгружает полную конфигурацию (CF). UUID берётся из заголовка CF в UTF-16LE, модуль — из `decode_stage_1/<uuid>.0/text`.
- Строк в модуле могут отличаться от git-репозитория: в серверной базе модуль 96 строк (в репо 186); вызов `ПриНачалеРаботыСистемы` на строке 64 (не 65). Всегда проверяй по CF через v8unpack (`python -m v8unpack -E`).

## Лицензии и благодарности

- Код этого репозитория (скилл, мост, документация) — MIT, см. `LICENSE`.
- Расширение [whiterabbit.1c-dev-tools](https://marketplace.visualstudio.com/items?itemName=whiterabbit.1c-dev-tools)
  — MIT © Andrew Ponomarev, включено как есть с оригинальной лицензией (`extension/LICENSE.txt`).
