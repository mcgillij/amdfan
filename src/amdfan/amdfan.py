#!/usr/bin/env python
""" Main amdfan script """
# noqa: E501
import logging
import os
import re
import sys
import atexit
import signal
import time
from typing import Any, List, Dict, Callable
import yaml
import numpy as np
from numpy import ndarray
import click

from rich.console import Console
from rich.traceback import install
from rich.prompt import Prompt
from rich.table import Table
from rich.live import Live
from rich.logging import RichHandler


install()  # install traceback formatter

CONFIG_LOCATIONS: List[str] = [
    "/etc/amdfan.yml",
]

DEBUG: bool = bool(os.environ.get("DEBUG", False))

ROOT_DIR: str = "/sys/class/drm"
HWMON_DIR: str = "device/hwmon"
PIDFILE_DIR: str = "/var/run"

LOGGER = logging.getLogger("rich")  # type: ignore
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

SYSTEMD_SERVICE: str = """[Unit]
Description=amdfan controller

[Service]
ExecStart=/usr/bin/amdfan --daemon
Restart=always

[Install]
WantedBy=multi-user.target
"""

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)

c: Console = Console(style="green on black")


class Card:
    """
    This class is used to map to each card that supports HWMON
    """

    HWMON_REGEX: str = r"^hwmon\d+$"
    AMD_FIELDS: List[str] = [
        "temp1_input",
        "pwm1_max",
        "pwm1_min",
        "pwm1_enable",
        "pwm1",
    ]

    def __init__(self, card_id: str) -> None:
        self._id = card_id

        for node in os.listdir(os.path.join(ROOT_DIR, self._id, HWMON_DIR)):
            if re.match(self.HWMON_REGEX, node):
                self._monitor = node
        self._endpoints = self._load_endpoints()

    def _verify_card(self) -> None:
        for endpoint in self.AMD_FIELDS:
            if endpoint not in self._endpoints:
                LOGGER.info("skipping card: %s missing endpoint %s", self._id, endpoint)
                raise FileNotFoundError

    def _load_endpoints(self) -> Dict:
        _endpoints = {}
        _dir = os.path.join(ROOT_DIR, self._id, HWMON_DIR, self._monitor)
        for endpoint in os.listdir(_dir):
            if endpoint not in ("device", "power", "subsystem", "uevent"):
                _endpoints[endpoint] = os.path.join(_dir, endpoint)
        return _endpoints

    def read_endpoint(self, endpoint: str) -> str:
        with open(self._endpoints[endpoint], "r") as endpoint_file:
            return endpoint_file.read()

    def write_endpoint(self, endpoint: str, data: int) -> int:
        try:
            with open(self._endpoints[endpoint], "w") as endpoint_file:
                return endpoint_file.write(str(data))
        except PermissionError:
            LOGGER.error("Failed writing to devfs file, are you running as root?")
            sys.exit(1)

    @property
    def fan_speed(self) -> int:
        try:
            return int(self.read_endpoint("fan1_input"))
        except (KeyError, OSError):  # better to return no speed then explode
            return 0

    @property
    def gpu_temp(self) -> float:
        return float(self.read_endpoint("temp1_input")) / 1000

    @property
    def fan_max(self) -> int:
        return int(self.read_endpoint("pwm1_max"))

    @property
    def fan_min(self) -> int:
        return int(self.read_endpoint("pwm1_min"))

    def set_system_controlled_fan(self, state: bool) -> None:

        system_controlled_fan = 2
        manual_control = 1

        self.write_endpoint(
            "pwm1_enable", system_controlled_fan if state else manual_control
        )

    def set_fan_speed(self, speed: int) -> int:
        if speed >= 100:
            speed = self.fan_max
        elif speed <= 0:
            speed = self.fan_min
        else:
            speed = int(self.fan_max / 100 * speed)
        self.set_system_controlled_fan(False)
        return self.write_endpoint("pwm1", speed)


class Scanner:  # pylint: disable=too-few-public-methods
    """Used to scan the available cards to see if they are usable"""

    CARD_REGEX: str = r"^card\d$"

    def __init__(self, cards=None) -> None:
        self.cards = self._get_cards(cards)

    def _get_cards(self, cards_to_scan):
        """
        only directories in ROOT_DIR that are card1, card0, card3 etc.
        :return: a list of initialized Card objects
        """
        cards = {}
        for node in os.listdir(ROOT_DIR):
            if re.match(self.CARD_REGEX, node):
                if cards_to_scan and node.lower() not in [
                    c.lower() for c in cards_to_scan
                ]:
                    continue
                try:
                    cards[node] = Card(node)
                except FileNotFoundError:
                    # if card lacks hwmon or required devfs files, its not
                    # amdgpu, and definitely not compatible with this software
                    continue
        return cards


class FanController:  # pylint: disable=too-few-public-methods
    """Used to apply the curve at regular intervals"""

    def __init__(self, config_path) -> None:
        self.config_path = config_path
        self.reload_config()
        self._last_temp = 0

    def reload_config(self, *_) -> None:
        config = load_config(self.config_path)
        self.apply(config)

    def apply(self, config) -> None:
        self._scanner = Scanner(config.get("cards"))
        if len(self._scanner.cards) < 1:
            LOGGER.error("no compatible cards found, exiting")
            sys.exit(1)
        self.curve = Curve(config.get("speed_matrix"))
        # default to 5 if frequency not set
        self._threshold = config.get("threshold")
        self._frequency = config.get("frequency", 5)

    def main(self) -> None:
        LOGGER.info("Starting amdfan")
        while True:
            for name, card in self._scanner.cards.items():
                apply = True
                temp = card.gpu_temp
                speed = int(self.curve.get_speed(int(temp)))
                if speed < 0:
                    speed = 4  # due to driver bug

                LOGGER.debug(
                    "%s: Temp %d, \
                            last temp: %d \
                            target fan speed: %d, \
                            fan speed %d, \
                            min: %d, max: %d",
                    name,
                    temp,
                    self._last_temp,
                    speed,
                    card.fan_speed,
                    card.fan_min,
                    card.fan_max,
                )
                if self._threshold and self._last_temp:

                    LOGGER.debug("threshold and last temp, checking")
                    low = self._last_temp - self._threshold
                    high = self._last_temp + self._threshold

                    LOGGER.debug("%d and %d and %d", low, high, temp)
                    if int(temp) in range(int(low), int(high)):
                        LOGGER.debug("temp in range doing nothing")
                        apply = False
                    else:
                        LOGGER.debug("temp out of range setting")
                        card.set_fan_speed(speed)
                        self._last_temp = temp
                        continue

                if apply:
                    card.set_fan_speed(speed)
                    self._last_temp = temp

            time.sleep(self._frequency)


class Curve:  # pylint: disable=too-few-public-methods
    """
    creates a fan curve based on user defined points
    """

    def __init__(self, points: list) -> None:
        self.points = np.array(points)
        self.temps = self.points[:, 0]
        self.speeds = self.points[:, 1]

        if np.min(self.speeds) < 0:
            raise ValueError(
                "Fan curve contains negative speeds, \
                        speed should be in [0,100]"
            )
        if np.max(self.speeds) > 100:
            raise ValueError(
                "Fan curve contains speeds greater than 100, \
                        speed should be in [0,100]"
            )
        if np.any(np.diff(self.temps) <= 0):
            raise ValueError(
                "Fan curve points should be strictly monotonically increasing, \
                        configuration error ?"
            )
        if np.any(np.diff(self.speeds) < 0):
            raise ValueError(
                "Curve fan speeds should be monotonically increasing, \
                        configuration error ?"
            )
        if np.min(self.speeds) <= 3:
            raise ValueError("Lowest speed value to be set to 4")  # Driver BUG

    def get_speed(self, temp: int) -> ndarray[Any, Any]:
        """
        returns a speed for a given temperature
        :param temp: int
        :return:
        """

        return np.interp(x=temp, xp=self.temps, fp=self.speeds)


def load_config(path) -> Callable:
    LOGGER.debug("loading config from %s", path)
    with open(path) as config_file:
        return yaml.safe_load(config_file)


@click.command()
@click.option(
    "--daemon", is_flag=True, default=False, help="Run as daemon applying the fan curve"
)
@click.option(
    "--monitor",
    is_flag=True,
    default=False,
    help="Run as a monitor showing temp and fan speed",
)
@click.option(
    "--manual",
    is_flag=True,
    default=False,
    help="Manually set the fan speed value of a card",
)
@click.option(
    "--configuration",
    is_flag=True,
    default=False,
    help="Prints out the default configuration for you to use",
)
@click.option(
    "--service",
    is_flag=True,
    default=False,
    help="Prints out the amdfan.service file to use with systemd",
)
def cli(
    daemon: bool, monitor: bool, manual: bool, configuration: bool, service: bool
) -> None:
    if daemon:
        run_as_daemon()
    elif monitor:
        monitor_cards()
    elif manual:
        set_fan_speed()
    elif configuration:
        print(DEFAULT_FAN_CONFIG)
    elif service:
        print(SYSTEMD_SERVICE)
    else:
        c.print("Try: --help to see the options")


def create_pidfile(pidfile: str) -> None:
    LOGGER.info("Creating pifile %s", pidfile)
    pid = os.getpid()
    with open(pidfile, "w") as file:
        file.write(str(pid))

    def remove_pidfile() -> None:
        if os.path.isfile(pidfile):
            os.remove(pidfile)

    atexit.register(remove_pidfile)
    LOGGER.info("Saved pidfile with running pid=%s", pid)


def run_as_daemon() -> None:
    create_pidfile(os.path.join(PIDFILE_DIR, "amdfan.pid"))

    config_path = None
    for location in CONFIG_LOCATIONS:
        if os.path.isfile(location):
            config_path = location
            break

    if config_path is None:
        LOGGER.info("No config found, creating one in %s", CONFIG_LOCATIONS[-1])
        with open(CONFIG_LOCATIONS[-1], "w") as config_file:
            config_file.write(DEFAULT_FAN_CONFIG)
            config_file.flush()

    controller = FanController(config_path)
    signal.signal(signal.SIGHUP, controller.reload_config)
    controller.main()


def show_table(cards: Dict) -> Table:
    table = Table(title="amdgpu")
    table.add_column("Card")
    table.add_column("fan_speed (RPM)")
    table.add_column("gpu_temp ℃")
    for card, card_value in cards.items():
        table.add_row(f"{card}", f"{card_value.fan_speed}", f"{card_value.gpu_temp}")
    return table


def monitor_cards() -> None:
    c.print("AMD Fan Control - ctrl-c to quit")
    scanner = Scanner()
    with Live(refresh_per_second=4) as live:
        while 1:
            time.sleep(0.4)
            live.update(show_table(scanner.cards))


def set_fan_speed() -> None:
    scanner = Scanner()
    card_to_set = Prompt.ask("Which card?", choices=scanner.cards.keys())
    while True:
        input_fan_speed = Prompt.ask("Fan speed, [1..100]% or 'auto'", default="auto")

        if input_fan_speed.isdigit():
            if int(input_fan_speed) >= 1 and int(input_fan_speed) <= 100:
                LOGGER.debug("good %d", int(input_fan_speed))
                break
        elif input_fan_speed == "auto":
            LOGGER.debug("fan speed set to auto")
            break
        c.print("maybe try picking one of the options")

    selected_card = scanner.cards.get(card_to_set)
    if not input_fan_speed.isdigit() and input_fan_speed == "auto":
        LOGGER.info("Setting fan speed to system controlled")
        selected_card.set_system_controlled_fan(True)
    else:
        LOGGER.info("Setting fan speed to %d", int(input_fan_speed))
        c.print(selected_card.set_fan_speed(int(input_fan_speed)))


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
