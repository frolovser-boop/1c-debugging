# -*- coding: utf-8 -*-
"""
Консольный интерфейс (CLI) для onec-debug.
"""

import argparse
import sys
import time

from .detector import detect_platform, list_known_bases, resolve_base
from .session import DebugSession
from .mcp_server import run_mcp_server


def cmd_list(args):
    """Выводит список известных баз."""
    bases = list_known_bases()
    if not bases:
        print("Базы 1С не найдены в ibases.v8i.")
        return

    print(f"=== Найдено баз 1С: {len(bases)} ===")
    for i, b in enumerate(bases, 1):
        btype = "ФАЙЛОВАЯ" if b.is_file else "СЕРВЕР"
        print(f"[{i:02d}] {b.name}")
        print(f"     Тип:   {btype} (infoBaseAlias: {b.alias})")
        print(f"     Подкл: {b.connect_str}")
        print(f"     Запуск:{b.launch_arg}")
        print()


def cmd_run(args):
    """Запускает сессию отладки из консоли."""
    base_info = resolve_base(args.base)
    print(f"Запуск отладки для базы: {base_info.name}")
    print(f"  Тип:       {'Файловая' if base_info.is_file else 'Серверная'}")
    print(f"  Alias:     {base_info.alias}")
    print(f"  Параметр:  {base_info.launch_arg}")

    session = DebugSession(
        base=base_info,
        user=args.user,
        password=args.password,
        thick_client=args.thick,
        dbgs_port=args.port
    )

    print("Инициализация RDBG и запуск клиента 1С...")
    session.start()

    print("Ожидание подключения отладочной цели (до 20 сек)...")
    target_id = session.wait_for_target(timeout_sec=20)
    if target_id:
        print(f"Цель успешно подключена! Target ID: {target_id}")
    else:
        print("Цель не появилась за время ожидания. Клиент запущен в фоне.")

    print("\nОтладка активна. Нажмите Ctrl+C для остановки и закрытия клиента.")
    try:
        while True:
            time.sleep(1)
            events = session.poll_events()
            if events:
                print(f"[СОБЫТИЕ] {events}")
                if "callStackFormed" in events:
                    st, stack = session.get_stack()
                    print(f"=== СТЕК ВЫЗОВОВ ===\n{stack}")
    except KeyboardInterrupt:
        print("\nОстановка сеанса...")
    finally:
        session.stop()
        print("Сеанс отладки завершён.")


def cmd_test(args):
    """Проверяет платформу и доступность dbgs."""
    print("=== Проверка окружения 1С ===")
    plat = detect_platform()
    if plat:
        print(f"Платформа 1С: версия {plat.version} в {plat.bin_dir}")
        print(f"  1cv8c.exe: {plat.enterprise or 'НЕ НАЙДЕН'}")
        print(f"  1cv8.exe:  {plat.thick_client or 'НЕ НАЙДЕН'}")
        print(f"  dbgs.exe:  {plat.debugger_server or 'НЕ НАЙДЕН'}")
    else:
        print("ВНИМАНИЕ: Установленная платформа 1С не обнаружена!")

    bases = list_known_bases()
    print(f"Зарегистрировано баз в ibases.v8i: {len(bases)}")
    print("Всё готово к работе.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="onec-debug: Автономная отладка 1С без Конфигуратора")
    subparsers = parser.add_subparsers(dest="subcommand", help="Команды")

    # list
    p_list = subparsers.add_parser("list", help="Список доступных баз 1С")
    p_list.set_defaults(func=cmd_list)

    # run
    p_run = subparsers.add_parser("run", help="Запустить сессию отладки базы")
    p_run.add_argument("base", help="Имя базы, путь к папке или строка подключения")
    p_run.add_argument("-u", "--user", default="Администратор", help="Пользователь 1С (default: Администратор)")
    p_run.add_argument("-p", "--password", default="", help="Пароль пользователя 1С")
    p_run.add_argument("--thick", action="store_true", help="Запустить толстый клиент (1cv8.exe)")
    p_run.add_argument("--port", type=int, default=1572, help="Порт dbgs.exe (default: 1572)")
    p_run.set_defaults(func=cmd_run)

    # test
    p_test = subparsers.add_parser("test", help="Проверка окружения платформы")
    p_test.set_defaults(func=cmd_test)

    # mcp
    p_mcp = subparsers.add_parser("mcp", help="Запуск MCP-сервера для AI-агентов (stdio)")
    p_mcp.set_defaults(func=lambda args: run_mcp_server())

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
