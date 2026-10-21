# MCP-сервер отладки 1C Dev Tools — карта

Факты сняты с VSIX whiterabbit.1c-dev-tools 2.10.11 (package.json, readme.md) и подтверждены живым handshake из сессии агента.

## Сервер

- Адрес: `http://127.0.0.1:18791/mcp`, транспорт Streamable HTTP. Адрес фиксированный (задокументирован в readme расширения).
- Поднимается при активации расширения в окне редактора (VS Code или Cursor); debug-тип `onec` (`onDebugResolve:onec`).
- Работает только по HTTP-протоколу отладки платформы. Если сервер отладки локальный — расширение пытается запустить `dbgs.exe` (bin платформы), удалённый — подключиться; режим отладки в Конфигураторе должен быть переключён на http.
- Параметры сервера отладки задаются в `env.json` проекта: `--debug-server`, `--debug-port-range` (напр. `1560:1591`); клиент запускается с флагами `/DEBUG`, `/DEBUGGERURL` (строки в бандле).

## Инструменты (11)

- `onec_debug_status` — есть ли сессия `type=onec`, имя сессии, launchConfigs, брейкпойнты, путь к JSON-снимку.
- `onec_debug_start` — запустить отладку (конфигурация `type=onec` из launch.json, параметр `configurationName`).
- `onec_debug_stop` — остановить текущую сессию.
- `onec_debug_set_breakpoint` — точка останова в модуле BSL; `path` — абсолютный или относительный путь к .bsl, + строка.
- `onec_debug_stack` — стек вызовов: модуль, строка, путь к .bsl (основная конфигурация и расширения).
- `onec_debug_variables` — локальные переменные верхнего кадра.
- `onec_debug_evaluate` — вычислить BSL-выражение в текущем кадре (как Watch/Реплика).
- `onec_debug_step_into` / `onec_debug_step_over` / `onec_debug_step_out` — шаги; возвращают обновлённый стек.
- `onec_debug_continue` — продолжить до следующего останова.

## Снимок для агента

При каждом останове стек пишется в `%TEMP%\1c-dev-tools-debug-snapshot.json` — можно читать из любой сессии на той же машине. Команда палитры «1C: Скопировать стек отладки для агента» (`1c-dev-tools.debug.copyAgentSnapshot`) кладёт тот же JSON в буфер обмена.

## launch.json (type=onec)

Известные из readme ключи: `type: "onec"`, `request: "launch" | "attach"`, `rootProject` (для отладки расширений — корень выгрузки: каталог с `src/cf`; расширение — `src/cfe/<ИмяРасширения>`), `autoAttachTypes` — типы целей RDBG для автоподключения: `Client`, `ManagedClient`, `WebClient`, `ComConnector`, `Server`, `ServerEmulation`, `WebService`, `HttpService`, `OData`, `Job`, `JobFileMode` и мобильные; пресеты `Client`/`Server` при отправке в сервер отладки разворачиваются в наборы подтипов.

Полный пример — секция «Параметры в launch.json» в `readme.md` внутри VSIX. При сборке launch.json читай его заново, ключи не придумывай.

Тайминги обмена с сервером отладки — настройки `1c-dev-tools.debug.timings.*` (settings редактора).

## Как снять факты заново (разбор VSIX)

VSIX — обычный zip: распаковать `python -m zipfile -e file.vsix dir/`. Факты лежат в `extension/package.json` (команды, конфиги, activationEvents), `extension/readme.md` (руководство, launch.json, MCP-раздел), `extension/env.json`, `extension/packagedef`. Бандл `dist/extension.js` читается как текст: grep по `onec_debug_`, номерам портов, флагам платформы даёт семантику инструментов.
