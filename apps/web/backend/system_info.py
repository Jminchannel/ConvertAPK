import os
import platform
import ctypes
from typing import Dict


def _memory_gb() -> str:
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            gb = status.ullTotalPhys / (1024 ** 3)
            return f"{gb:.1f} GB"
        return ""
    if hasattr(os, "sysconf"):
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        gb = (page_size * pages) / (1024 ** 3)
        return f"{gb:.1f} GB"
    return ""


def get_system_info() -> Dict[str, str]:
    cpu = platform.processor() or platform.machine()
    cores = os.cpu_count() or 0
    ram = _memory_gb()
    return {
        "cpu": cpu,
        "cores": str(cores),
        "ram": ram,
        "os": f"{platform.system()} {platform.release()}",
    }
