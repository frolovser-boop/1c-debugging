# -*- coding: utf-8 -*-
"""
Автообнаружение окружения 1С (Кроссплатформенное: Windows и Linux):
- Поиск установленных платформ 1С (8.3.x).
- Парсинг зарегистрированных баз из ibases.v8i.
- Нормализация параметров подключения (файловые vs серверные базы, расчет infoBaseAlias).
"""

import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class PlatformInfo:
    version: str
    bin_dir: str
    enterprise: Optional[str]
    thick_client: Optional[str]
    debugger_server: Optional[str]


@dataclass
class BaseInfo:
    name: str
    connect_str: str
    is_file: bool
    alias: str
    launch_arg: str  # например, /F"..." или /S"..."
    file_path: Optional[str] = None
    server_host: Optional[str] = None
    server_ref: Optional[str] = None


def detect_platform(preferred_version: Optional[str] = None) -> Optional[PlatformInfo]:
    """Находит установленные версии платформы 1С и возвращает пути к исполняемым файлам (Windows и Linux)."""
    is_windows = sys.platform.startswith("win")
    
    if is_windows:
        search_dirs = [
            r"C:\Program Files\1cv8",
            r"C:\Program Files (x86)\1cv8"
        ]
        exe_ext = ".exe"
    else:
        search_dirs = [
            "/opt/1cv8/x86_64",
            "/opt/1cv8/i386",
            "/opt/1C/v8.3/x86_64",
            "/opt/1C/v8.3/i386",
            "/opt/1cv8/common"
        ]
        exe_ext = ""

    found_versions = []
    version_regex = re.compile(r"^8\.3\.\d+\.\d+$")

    for base_dir in search_dirs:
        if not os.path.exists(base_dir):
            continue
        try:
            for entry in os.listdir(base_dir):
                full_path = os.path.join(base_dir, entry)
                # На Windows bin_path = <ver>/bin, на Linux часто сразу в папке версии или в bin
                if os.path.isdir(os.path.join(full_path, "bin")):
                    bin_path = os.path.join(full_path, "bin")
                elif os.path.isdir(full_path) and version_regex.match(entry):
                    bin_path = full_path
                else:
                    continue

                if version_regex.match(entry):
                    ver_tuple = tuple(int(x) for x in entry.split("."))
                    found_versions.append((ver_tuple, entry, bin_path))
        except Exception:
            continue

    if not found_versions:
        # Попробуем поискать по PATH
        which_cmd = "where" if is_windows else "which"
        return None

    # Сортируем версии по возрастанию
    found_versions.sort(key=lambda x: x[0])

    chosen_bin = None
    chosen_ver = None

    if preferred_version:
        for ver_tup, ver_str, bpath in found_versions:
            if ver_str == preferred_version or ver_str.startswith(preferred_version):
                chosen_bin = bpath
                chosen_ver = ver_str
                break

    if not chosen_bin:
        chosen_ver = found_versions[-1][1]
        chosen_bin = found_versions[-1][2]

    c_exe = os.path.join(chosen_bin, f"1cv8c{exe_ext}")
    t_exe = os.path.join(chosen_bin, f"1cv8{exe_ext}")
    d_exe = os.path.join(chosen_bin, f"dbgs{exe_ext}")

    return PlatformInfo(
        version=chosen_ver,
        bin_dir=chosen_bin,
        enterprise=c_exe if os.path.exists(c_exe) else None,
        thick_client=t_exe if os.path.exists(t_exe) else None,
        debugger_server=d_exe if os.path.exists(d_exe) else None
    )


def list_known_bases() -> List[BaseInfo]:
    """Считывает все зарегистрированные базы пользователя из ibases.v8i (Windows и Linux)."""
    home = os.path.expanduser("~")
    appdata = os.environ.get("APPDATA", "")
    local_appdata = os.environ.get("LOCALAPPDATA", "")

    paths_to_try = [
        # Windows
        os.path.join(appdata, "1C", "1CEStart", "ibases.v8i"),
        os.path.join(local_appdata, "1C", "1CEStart", "ibases.v8i"),
        # Linux
        os.path.join(home, ".1C", "1CEStart", "ibases.v8i"),
        os.path.join(home, ".1C", "1client", "ibases.v8i"),
        os.path.join(home, ".1cv8", "1C", "1c", "ibases.v8i"),
        os.path.join(home, ".1cv8", "1cv8.v8i"),
    ]
    
    file_path = None
    for p in paths_to_try:
        if p and os.path.exists(p):
            file_path = p
            break

    if not file_path:
        return []

    try:
        with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read()
    except Exception:
        return []

    bases = []
    current_name = None
    current_params: Dict[str, str] = {}

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            if current_name and "Connect" in current_params:
                info = _parse_connect_string(current_name, current_params["Connect"])
                if info:
                    bases.append(info)
            current_name = line[1:-1]
            current_params = {}
        elif current_name and "=" in line:
            k, v = line.split("=", 1)
            current_params[k.strip()] = v.strip()

    if current_name and "Connect" in current_params:
        info = _parse_connect_string(current_name, current_params["Connect"])
        if info:
            bases.append(info)

    return bases


def _parse_connect_string(name: str, connect_str: str) -> Optional[BaseInfo]:
    """Парсит строку соединения 1С (File=... или Srvr=...;Ref=...;)"""
    clean_conn = connect_str.strip().rstrip(";")
    
    # Файловая база
    m_file = re.search(r'File="?([^";]+)"?', clean_conn, re.IGNORECASE)
    if m_file:
        fpath = m_file.group(1).strip()
        return BaseInfo(
            name=name,
            connect_str=connect_str,
            is_file=True,
            alias="DefAlias",
            launch_arg=f'/F"{fpath}"',
            file_path=fpath
        )

    # Серверная база
    m_srvr = re.search(r'Srvr="?([^";]+)"?', clean_conn, re.IGNORECASE)
    m_ref = re.search(r'Ref="?([^";]+)"?', clean_conn, re.IGNORECASE)
    if m_srvr and m_ref:
        srvr = m_srvr.group(1).strip()
        ref = m_ref.group(1).strip()
        if ":" not in srvr:
            cluster_str = f"{srvr}:1541"
        else:
            cluster_str = srvr
        return BaseInfo(
            name=name,
            connect_str=connect_str,
            is_file=False,
            alias=ref,
            launch_arg=f'/S"{cluster_str}\\{ref}"',
            server_host=cluster_str,
            server_ref=ref
        )

    return None


def resolve_base(identifier: str) -> BaseInfo:
    """
    Разрешает базу по идентификатору:
    1. Имени в списке ibases.v8i (точному или частичному).
    2. Пути к локальной папке (файловая база).
    3. Строке соединения (Srvr=...;Ref=... или host\ref).
    """
    known = list_known_bases()
    id_lower = identifier.lower().strip()

    for b in known:
        if b.name.lower() == id_lower:
            return b

    for b in known:
        if id_lower in b.name.lower():
            return b

    if os.path.exists(identifier) and os.path.isdir(identifier):
        abs_p = os.path.abspath(identifier)
        return BaseInfo(
            name=os.path.basename(abs_p),
            connect_str=f'File="{abs_p}";',
            is_file=True,
            alias="DefAlias",
            launch_arg=f'/F"{abs_p}"',
            file_path=abs_p
        )

    m_f = re.search(r'File="?([^";]+)"?', identifier, re.IGNORECASE)
    if m_f:
        fpath = m_f.group(1).strip()
        return BaseInfo(
            name=os.path.basename(fpath.rstrip("\\/")),
            connect_str=identifier,
            is_file=True,
            alias="DefAlias",
            launch_arg=f'/F"{fpath}"',
            file_path=fpath
        )

    m_s = re.search(r'Srvr="?([^";]+)"?', identifier, re.IGNORECASE)
    m_r = re.search(r'Ref="?([^";]+)"?', identifier, re.IGNORECASE)
    if m_s and m_r:
        srvr = m_s.group(1).strip()
        ref = m_r.group(1).strip()
        cluster_str = srvr if ":" in srvr else f"{srvr}:1541"
        return BaseInfo(
            name=ref,
            connect_str=identifier,
            is_file=False,
            alias=ref,
            launch_arg=f'/S"{cluster_str}\\{ref}"',
            server_host=cluster_str,
            server_ref=ref
        )

    if "\\" in identifier:
        host_part, ref_part = identifier.split("\\", 1)
        host_part = host_part.strip()
        ref_part = ref_part.strip()
        cluster_str = host_part if ":" in host_part else f"{host_part}:1541"
        return BaseInfo(
            name=ref_part,
            connect_str=f'Srvr="{cluster_str}";Ref="{ref_part}";',
            is_file=False,
            alias=ref_part,
            launch_arg=f'/S"{cluster_str}\\{ref_part}"',
            server_host=cluster_str,
            server_ref=ref_part
        )

    return BaseInfo(
        name=identifier,
        connect_str=f'Srvr="localhost:1541";Ref="{identifier}";',
        is_file=False,
        alias=identifier,
        launch_arg=f'/S"localhost:1541\\{identifier}"',
        server_host="localhost:1541",
        server_ref=identifier
    )
