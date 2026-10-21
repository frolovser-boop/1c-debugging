# -*- coding: utf-8 -*-
"""
Управление жизненным циклом сеанса отладки:
- Автозапуск и контроль сервера отладки (dbgs.exe).
- Инициализация и регистрация UI.
- Запуск тонкого / толстого клиента 1С с корректными параметрами отладки.
- Обнаружение и привязка целей.
- Обработка точек останова, шагов и стека вызовов.
- Корректное завершение и освобождение ресурсов.
"""

import os
import re
import socket
import subprocess
import time
import uuid
from typing import Dict, List, Optional, Tuple, Any, Callable

from .detector import BaseInfo, PlatformInfo, detect_platform, resolve_base
from .rdbg import RdbgClient


def is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """Проверяет доступность TCP-порта."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class DebugSession:
    """Сеанс отладки конкретной базы 1С."""

    def __init__(
        self,
        base: BaseInfo,
        platform: Optional[PlatformInfo] = None,
        dbgs_port: int = 1572,
        user: str = "Администратор",
        password: str = "",
        thick_client: bool = False,
        auto_manage_dbgs: bool = True
    ):
        self.base = base
        self.platform = platform or detect_platform()
        if not self.platform:
            raise RuntimeError("Не найдена установленная платформа 1С:Предприятие 8.3.")

        self.dbgs_port = dbgs_port
        self.user = user
        self.password = password
        self.thick_client = thick_client
        self.auto_manage_dbgs = auto_manage_dbgs

        self.ui_id = str(uuid.uuid4())
        self.client = RdbgClient(host="127.0.0.1", port=self.dbgs_port)

        self._dbgs_proc: Optional[subprocess.Popen] = None
        self._app_proc: Optional[subprocess.Popen] = None
        self._targets: List[Dict[str, str]] = []
        self._active_target_id: Optional[str] = None
        self._is_active = False

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def active_target_id(self) -> Optional[str]:
        return self._active_target_id

    def start(self, initial_breakpoints: Optional[List[Dict[str, Any]]] = None) -> bool:
        """Запускает сессию отладки."""
        # 1. Проверяем или запускаем dbgs.exe
        if not is_port_open("127.0.0.1", self.dbgs_port):
            if self.auto_manage_dbgs and self.platform.debugger_server:
                dbgs_cmd = [
                    self.platform.debugger_server,
                    "--addr", "127.0.0.1",
                    "--port", str(self.dbgs_port)
                ]
                self._dbgs_proc = subprocess.Popen(dbgs_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(1.0)
                if not is_port_open("127.0.0.1", self.dbgs_port):
                    raise RuntimeError(f"Не удалось запустить dbgs.exe на порту {self.dbgs_port}")
            else:
                raise RuntimeError(f"Сервер отладки dbgs.exe не отвечает на 127.0.0.1:{self.dbgs_port}")

        # 2. Регистрируем UI
        status, resp = self.client.attach_debug_ui(self.base.alias, self.ui_id)
        if status != 200 or "registered" not in resp:
            # Предупреждение, но продолжаем
            pass

        # 3. Настраиваем типы процессов
        self.client.set_auto_attach_settings(self.base.alias, self.ui_id)

        # 4. Устанавливаем начальные точки останова (если есть)
        if initial_breakpoints:
            self.set_breakpoints(initial_breakpoints)

        # 5. Запускаем клиент 1С
        exe_path = self.platform.thick_client if self.thick_client else self.platform.enterprise
        if not exe_path or not os.path.exists(exe_path):
            raise RuntimeError(f"Исполняемый файл 1С не найден: {exe_path}")

        # Формируем аргументы запуска
        cmd = [
            exe_path,
            "ENTERPRISE",
            self.base.launch_arg,
            f'/N"{self.user}"',
        ]
        if self.password:
            cmd.append(f'/P"{self.password}"')

        # Флаги отладки
        cmd.extend([
            "/DEBUG",
            "-http",
            "/DEBUGGERURL",
            f"http://127.0.0.1:{self.dbgs_port}",
            "/DisableStartupMessages"
        ])

        self._app_proc = subprocess.Popen(cmd)
        self._is_active = True
        return True

    def wait_for_target(self, timeout_sec: int = 30) -> Optional[str]:
        """Ожидает регистрации отладочной цели в dbgs и привязывает её."""
        t_start = time.time()
        while time.time() - t_start < timeout_sec:
            # Обновляем регистрацию UI
            self.client.attach_debug_ui(self.base.alias, self.ui_id)
            targets = self.client.get_dbg_targets(self.base.alias, self.ui_id)
            if targets:
                self._targets = targets
                self._active_target_id = targets[0]["id"]
                # Привязываем цель
                self.client.attach_detach_targets(self.base.alias, self.ui_id, attach=[self._active_target_id])
                # Запускаем таргет
                self.client.start_target(self._active_target_id)
                return self._active_target_id
            time.sleep(1.0)
        return None

    def set_breakpoints(self, breakpoints: List[Dict[str, Any]]) -> Tuple[int, str]:
        """Устанавливает точки останова."""
        return self.client.set_breakpoints(self.base.alias, self.ui_id, breakpoints)

    def poll_events(self) -> List[str]:
        """Опрашивает сервер на наличие событий отладки (останов, старт, завершение)."""
        events = []
        if self._active_target_id:
            st_tgt, r_tgt = self.client.ping_target(self._active_target_id)
            if "callStackFormed" in r_tgt:
                events.append("callStackFormed")
            if "targetQuit" in r_tgt:
                events.append("targetQuit")

        st_ui, r_ui = self.client.ping_ui(self.base.alias, self.ui_id)
        if "callStackFormed" in r_ui:
            events.append("callStackFormed")
        if "targetStarted" in r_ui:
            events.append("targetStarted")

        return events

    def get_stack(self) -> Tuple[int, str]:
        """Возвращает стек вызовов остановленной цели."""
        if not self._active_target_id:
            return 0, "Нет активной отладочной цели."
        return self.client.get_call_stack(self.base.alias, self.ui_id, self._active_target_id)

    def continue_execution(self) -> Tuple[int, str]:
        """Продолжает выполнение остановленной цели."""
        if not self._active_target_id:
            return 0, "Нет активной отладочной цели."
        return self.client.step(self.base.alias, self.ui_id, self._active_target_id, action="Continue")

    def step_over(self) -> Tuple[int, str]:
        """Шаг через (StepOver)."""
        if not self._active_target_id:
            return 0, "Нет активной отладочной цели."
        return self.client.step(self.base.alias, self.ui_id, self._active_target_id, action="Step")

    def step_into(self) -> Tuple[int, str]:
        """Шаг с заходом (StepInto)."""
        if not self._active_target_id:
            return 0, "Нет активной отладочной цели."
        return self.client.step(self.base.alias, self.ui_id, self._active_target_id, action="StepIn")

    def step_out(self) -> Tuple[int, str]:
        """Шаг из (StepOut)."""
        if not self._active_target_id:
            return 0, "Нет активной отладочной цели."
        return self.client.step(self.base.alias, self.ui_id, self._active_target_id, action="StepOut")

    def stop(self):
        """Останавливает сессию и завершает процессы."""
        self._is_active = False
        if self._app_proc:
            try:
                self._app_proc.terminate()
                self._app_proc.wait(timeout=3)
            except Exception:
                try:
                    self._app_proc.kill()
                except Exception:
                    pass
            self._app_proc = None

        if self._dbgs_proc:
            try:
                self._dbgs_proc.terminate()
                self._dbgs_proc.wait(timeout=2)
            except Exception:
                try:
                    self._dbgs_proc.kill()
                except Exception:
                    pass
            self._dbgs_proc = None
