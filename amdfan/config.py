#!/usr/bin/env python
"""holds the configuration for the amdfan runtime"""
import logging
import os
from typing import List

from rich.logging import RichHandler

CONFIG_LOCATIONS: List[str] = [
    "/etc/amdfan.yml",
]

DEBUG: bool = bool(os.environ.get("DEBUG", False))
LOGGER = logging.getLogger("rich")  # type: ignore
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)


ROOT_DIR: str = "/sys/class/drm"
HWMON_DIR: str = "device/hwmon"
PIDFILE_DIR: str = "/var/run"
