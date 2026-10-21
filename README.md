# 1C Debugging (onec-debug)

**Универсальный инструмент отладки 1С:Предприятия без Конфигуратора для AI-агентов и разработчиков.**

Поддерживает работу с **любыми информационными базами** (файловыми и серверными), автоматическое обнаружение платформы 1С и баз пользователя, а также интеграцию с любыми AI-агентами по протоколу MCP.

---

## Возможности

* 🚀 **Два режима работы:**
  1. **Автономный Headless RDBG (чистый Python, без VS Code):** прямое общение с `dbgs.exe` по протоколу HTTP/XML. Не требует графического интерфейса, Node.js или установленного VS Code. Подходит для CI/CD, серверов и автономных агентов.
  2. **Интеграция с VS Code / Cursor (1C Dev Tools):** работа через официальный VSIX с графическим отображением отладки в редакторе кода.
* 📦 **Поддержка любых баз 1С:**
  * **Автообнаружение:** автоматический парсинг баз из `%APPDATA%\1C\1CEStart\ibases.v8i` (достаточно указать имя базы из списка).
  * **Файловые базы:** пути к каталогам (`/F"..."`, автоматический `infoBaseAlias = "DefAlias"`).
  * **Серверные базы:** кластерные строки подключения (`/S"host:port\name"`, автоматический `infoBaseAlias = "<имя базы>"`).
* 🤖 **MCP-сервер для AI-агентов:**
  * Позволяет агентам (Hermes, Claude Code, Cursor, Cline, Antigravity) управлять процессом отладки через стандартные JSON-RPC вызовы (старт, брейкпоинты, стек вызовов, пошаговое выполнение, продолжить, остановить).
* 🔍 **Автопоиск платформы 1С:**
  * Автоматический выбор последней установленной версии платформы (`8.3.x`) и исполняемых файлов `1cv8c.exe`, `1cv8.exe`, `dbgs.exe`.

---

## Архитектура

```
                        ┌────────────────────────────────────────────────────────┐
                        │             AI-Агент / Пользователь                    │
                        │   (Hermes, Claude Code, Cursor, Cline, Antigravity)    │
                        └──────────────────────────┬─────────────────────────────┘
                                                   │
                  ┌────────────────────────────────┴────────────────────────────────┐
                  ▼                                                                 ▼
      [Режим А: Headless Python]                                      [Режим Б: VS Code / Cursor]
       python -m onec_debug mcp                                        whiterabbit.1c-dev-tools (VSIX)
       (чистый Python, RDBG HTTP)                                      (порт 18791 + stdio мост)
                  │                                                                 │
                  └────────────────────────────────┬────────────────────────────────┘
                                                   │ RDBG HTTP (порт 1572 / 1560)
                                                   ▼
                                       ┌───────────────────────┐
                                       │       dbgs.exe        │
                                       │ (сервер отладки 1С)   │
                                       └───────────┬───────────┘
                                                   │ /DEBUG -http /DEBUGGERURL
                                                   ▼
                                       ┌───────────────────────┐
                                       │  Клиент / Сервер 1С   │
                                       │ 1cv8c.exe / rphost    │
                                       └───────────────────────┘
```

---

## Быстрый старт

### 1. Установка пакета

```bash
git clone https://gitlab.tools.russianpost.ru/1c/common/ai/mcp/1c-debugging.git
# или: git clone https://github.com/frolovser-boop/1c-debugging.git

cd 1c-debugging
pip install -e .
```
*(Либо можно использовать без установки в pip, запуская `python -m onec_debug ...` из папки репозитория).*

---

### 2. Консольный интерфейс (CLI)

#### Проверка установленной платформы и путей:
```bash
onec-debug test
# или: python -m onec_debug test
```

#### Список доступных баз из списка 1С (`ibases.v8i`):
```bash
onec-debug list
```
*Пример вывода:*
```text
=== Найдено баз 1С: 13 ===
[01] scenario
     Тип:   СЕРВЕР (infoBaseAlias: scenario)
     Подкл: Srvr="localhost";Ref="scenario";
     Запуск:/S"localhost:1541\scenario"

[02] АСБНУ
     Тип:   ФАЙЛОВАЯ (infoBaseAlias: DefAlias)
     Подкл: File="E:\1C_Base\ASBNU";
     Запуск:/F"E:\1C_Base\ASBNU"
```

#### Запуск отладки для любой базы:
```bash
# По имени из списка ibases.v8i:
onec-debug run "scenario"

# Серверная база по имени:
onec-debug run --base "scenario" -u "Администратор"

# Файловая база по пути к папке:
onec-debug run "E:\1C_Base\ASBNU"

# Серверная база по строке подключения:
onec-debug run 'Srvr="localhost:1541";Ref="scenario";'
```

---

## Подключение к AI-агентам (MCP)

### Режим А: Автономный MCP-сервер (без VS Code)

Добавьте в конфигурацию вашего агента:

**Claude Desktop / Claude Code (`claude_desktop_config.json`):**
```json
{
  "mcpServers": {
    "1c-debug": {
      "command": "python",
      "args": ["-m", "onec_debug", "mcp"],
      "cwd": "C:/путь/к/1c-debugging"
    }
  }
}
```

**Cursor / Cline (`settings.json`):**
```json
{
  "mcpServers": {
    "1c-debug": {
      "command": "onec-debug",
      "args": ["mcp"]
    }
  }
}
```

**Hermes Agent:**
Скопируйте директорию `skill/1c-debugging` в профиль агента:
`C:\Hermes\profiles\<profile>\skills\1c-debugging`

#### Доступные MCP-инструменты:
1. `onec_list_bases` — список всех доступных баз с параметрами подключения.
2. `onec_start_debugging` — запуск отладки (принимает имя базы, путь или строку подключения).
3. `onec_set_breakpoints` — установка точек останова (object_id, line).
4. `onec_get_targets` — список активных целей (клиент, сервер, фоновые задания).
5. `onec_get_call_stack` — стек вызовов при останове.
6. `onec_continue` — продолжить выполнение (F5).
7. `onec_step_over` / `step_into` / `step_out` — пошаговое выполнение.
8. `onec_stop_debugging` — завершение отладки и закрытие процессов.

---

### Режим Б: Использование с VS Code / Cursor (через VSIX)

1. Установите расширение:
   ```bash
   code --install-extension extension/whiterabbit.1c-dev-tools-2.10.11.vsix
   ```
2. Откройте проект с файлом `.vscode/launch.json`:
   ```json
   {
     "version": "0.2.0",
     "configurations": [
       {
         "type": "onec",
         "request": "launch",
         "name": "1C: Отладка",
         "debugServerHost": "localhost",
         "debugServerPort": 1572,
         "infoBaseAlias": "scenario",
         "autoAttachTypes": ["Client", "Server", "Job"]
       }
     ]
   }
   ```
3. Расширение автоматически поднимет MCP-сервер на порту `18791`. Подключение stdio-моста:
   ```json
   {
     "mcpServers": {
       "1c-debug-vscode": {
         "command": "python",
         "args": ["C:/путь/к/1c-debugging/mcp-bridge/onec_debug_stdio.py"]
       }
     }
   }
   ```

---

## Правила работы с протоколом RDBG (1С 8.3.27)

1. **infoBaseAlias:**
   * Для **файловых баз** значение строго фиксировано: `DefAlias`.
   * Для **серверных баз** значение обязано быть равно **имени базы в кластере** (например, `scenario`). При значении `DefAlias` сервер вернет 0 целей.
2. **Параметры запуска клиента 1С:**
   * Протокол должен совпадать: на сервере `http` и в клиенте `-http`.
   * Параметр `/DEBUGGERURL`: строго `http://127.0.0.1:1572` **без суффикса `/e1crdbg`**.
3. **PropertyID модулей:**
   * Модуль управляемого приложения: `d22e852a-cf8a-4f77-8ccb-3548e7792bea`.

---

## Структура проекта

```
1c-debugging/
├── onec_debug/                 # Основной пакет автономной отладки
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                  # Консольный интерфейс (list, run, test, mcp)
│   ├── detector.py             # Автопоиск платформы 1С и баз из ibases.v8i
│   ├── rdbg.py                 # Чистая реализация RDBG HTTP протокола
│   ├── session.py              # Управление сеансом отладки и процессами
│   └── mcp_server.py           # Стандартный MCP-сервер для AI-агентов
├── extension/                  # VSIX-расширение для VS Code (1C Dev Tools)
│   ├── whiterabbit.1c-dev-tools-2.10.11.vsix
│   └── LICENSE.txt
├── mcp-bridge/                 # Stdio-мост для VS Code MCP
│   └── onec_debug_stdio.py
├── skill/                      # Готовый навык (skill) для агентов Hermes
│   └── 1c-debugging/
│       ├── SKILL.md
│       ├── references/
│       └── scripts/
├── pyproject.toml              # Спецификация Python-пакета
├── setup.py                    # Скрипт установки pip
├── README.md                   # Руководство пользователя
└── LICENSE                     # Лицензия MIT
```

---

## Лицензия

MIT License. См. [LICENSE](LICENSE) для подробностей.
Расширение 1C Dev Tools (в каталоге `extension/`) распространяется по лицензии MIT (© Andrew Ponomarev).
