#!/usr/bin/env python
"""manages the amd gpu fans on your system"""
import atexit
import os
import re
import signal
import sys
import threading
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import yaml
from numpy import ndarray

from .config import CONFIG_LOCATIONS, HWMON_DIR, LOGGER, ROOT_DIR
from .defaults import DEFAULT_FAN_CONFIG


def create_pidfile(pidfile: str) -> None:
    LOGGER.info("Creating pifile %s", pidfile)
    pid = os.getpid()
    with open(pidfile, "w", encoding="utf8") as file:
        file.write(str(pid))

    def remove_pidfile() -> None:
        if os.path.isfile(pidfile):
            os.remove(pidfile)

    atexit.register(remove_pidfile)
    LOGGER.info("Saved pidfile with running pid=%s", pid)


def report_ready(fd: int) -> None:
    os.write(fd, b"READY=1\n")


def daemonize(stdin="/dev/null", stdout="/dev/null", stderr="/dev/null") -> None:
    try:
        pid = os.fork()
        if pid > 0:
            os._exit(0)
    except OSError as e:
        raise Exception("Unable to background amdfan: %s" % e)

    os.chdir("/")
    os.setsid()
    os.umask(0)

    try:
        pid = os.fork()
        if pid > 0:
            os._exit(0)
    except OSError as e:
        raise Exception("Unable to daemonize amdfan: %s" % e)

    redirect_fd(stdin, stdout, stderr)


def redirect_fd(stdin="/dev/null", stdout="/dev/null", stderr="/dev/null"):
    sys.stdout.flush()
    sys.stderr.flush()
    with open(stdin, "r") as f:
        os.dup2(f.fileno(), sys.stdin.fileno())

    with open(stdout, "a+") as f:
        os.dup2(f.fileno(), sys.stdout.fileno())
    with open(stderr, "a+") as f:
        os.dup2(f.fileno(), sys.stderr.fileno())


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
        with open(self._endpoints[endpoint], "r", encoding="utf8") as endpoint_file:
            return endpoint_file.read()

    def write_endpoint(self, endpoint: str, data: int) -> int:
        # debug here, troubleshooting 7900xtx
        # print("writing to endpoint", endpoint, "data", data)
        try:
            with open(self._endpoints[endpoint], "w", encoding="utf8") as endpoint_file:
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
            speed = int((self.fan_max - self.fan_min) / 100 * speed + self.fan_min)

        self.set_system_controlled_fan(False)
        return self.write_endpoint("pwm1", speed)


class Scanner:  # pylint: disable=too-few-public-methods
    """Used to scan the available cards to see if they are usable"""

    CARD_REGEX: str = r"^card+\d$"
    cards: Dict[str, Card]

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

    _scanner: Scanner
    _curve: Curve
    _threshold: int
    _frequency: int

    def __init__(self, config_path, notification_fd=None) -> None:
        self.config_path = config_path
        self.load_config()
        self._last_temp = 0
        self._ready_fd = notification_fd
        self._running = False
        self._stop_event = threading.Event()

    def reload_config(self, *_) -> None:
        LOGGER.info("Received request to reload config")
        self.load_config()

    def terminate(self, *_) -> None:
        LOGGER.info("Shutting down controller")
        self._running = False
        self._stop_event.set()

    def load_config(self) -> None:
        LOGGER.info("Loading configuration")
        config = load_config(self.config_path)
        self.apply(config)
        LOGGER.info("Configuration succesfully loaded")

    def apply(self, config) -> None:
        self._scanner = Scanner(config.get("cards"))
        if len(self._scanner.cards) < 1:
            LOGGER.error("no compatible cards found, exiting")
            sys.exit(1)
        self._curve = Curve(config.get("speed_matrix"))
        self._threshold = config.get("threshold", 0)
        self._frequency = config.get("frequency", 5)

    def main(self) -> None:
        if self._ready_fd is not None:
            report_ready(self._ready_fd)

        self._running = True
        LOGGER.info("Controller is running")
        while self._running:
            for name, card in self._scanner.cards.items():
                # print("refreshing card", name, card)
                self.refresh_card(name, card)

            self._stop_event.wait(self._frequency)
        LOGGER.info("Stopped controller")

    def refresh_card(self, name, card):
        # print("refreshing card", name, card)
        apply = True
        temp = card.gpu_temp
        speed = int(self._curve.get_speed(int(temp)))
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

        # print(f"fan_min: {card.fan_min}, fan_max: {card.fan_max}")

        if self._threshold and self._last_temp:

            LOGGER.debug("threshold and last temp, checking")
            low = self._last_temp - self._threshold
            high = self._last_temp + self._threshold

            LOGGER.debug("%d and %d and %d", low, high, temp)
            if int(temp) in range(int(low), int(high)):
                LOGGER.debug("temp in range, doing nothing")
                apply = False
            else:
                LOGGER.debug("temp out of range, setting")
                card.set_fan_speed(speed)
                self._last_temp = temp
                return

        if apply:
            card.set_fan_speed(speed)
            self._last_temp = temp

    @classmethod
    def start_manager(
        cls,
        notification_fd: Optional[int] = None,
        pidfile: Optional[str] = None,
        daemon=False,
        logfile=None,
    ) -> None:
        if daemon:
            daemonize(stdout=logfile, stderr=logfile)
        elif logfile:
            redirect_fd(stdout=logfile, stderr=logfile)

        if logfile:
            open(logfile, "w").close()  # delete old logs

        LOGGER.info("Launching the amdfan controller")

        if pidfile:
            if os.path.isfile(pidfile):
                with open(pidfile, "r") as f:
                    LOGGER.warning(
                        "Already found a pidfile for amdfan. Old PID was: %s",
                        f.read(),
                    )
            create_pidfile(pidfile)

        config_path = None
        for location in CONFIG_LOCATIONS:
            if os.path.isfile(location):
                config_path = location
                LOGGER.info("Found configuration file at %s", config_path)
                break

        if config_path is None:
            LOGGER.info("No config found, creating one in %s", CONFIG_LOCATIONS[-1])
            with open(CONFIG_LOCATIONS[-1], "w", encoding="utf8") as config_file:
                config_file.write(DEFAULT_FAN_CONFIG)
                config_file.flush()

        controller = cls(config_path, notification_fd=notification_fd)
        signal.signal(signal.SIGHUP, controller.reload_config)
        signal.signal(signal.SIGTERM, controller.terminate)
        signal.signal(signal.SIGINT, controller.terminate)
        controller.main()
        LOGGER.info("Goodbye")


def load_config(path) -> Callable:
    LOGGER.debug("loading config from %s", path)
    with open(path, encoding="utf8") as config_file:
        return yaml.safe_load(config_file)
