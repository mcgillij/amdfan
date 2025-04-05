#!/usr/bin/env python
"""includes strings to suggest default files"""

from typing import Dict

DEFAULT_FAN_CONFIG: str = """#Fan Control Matrix.
# [<Temp in C>,<Fanspeed in %>]
speed_matrix:
- [4, 4]
- [30, 33]
- [45, 50]
- [60, 66]
- [65, 69]
- [70, 75]
- [75, 89]
- [80, 100]

# Current Min supported value is 4 due to driver bug
#
# Optional configuration options
#
# Allows for some leeway +/- temp, as to not constantly change fan speed
# threshold: 4
#
# Frequency will change how often we probe for the temp
# frequency: 5
#
# While frequency and threshold are optional, I highly recommend finding
# settings that work for you. I've included the defaults I use above.
#
# cards:
# can be any card returned from `ls /sys/class/drm | grep "^card[[:digit:]]$"`
# - card0
"""

SERVICES: Dict[str, str] = {
    "systemd": """\
[Unit]
Description=amdfan controller

[Service]
ExecStart=/usr/bin/amdfan daemon
ExecReload=kill -HUP $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
"""
}
