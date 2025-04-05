#!/usr/bin/env python
"""entry point for amdfan"""
# noqa: E501
import os
import signal
import sys
import time
from typing import Dict

import click
from rich.console import Console
from rich.live import Live
from rich.prompt import Prompt
from rich.table import Table
from rich.traceback import install

from .config import LOGGER, PIDFILE_DIR
from .controller import FanController, Scanner
from .defaults import DEFAULT_FAN_CONFIG, SERVICES

install()  # install traceback formatter

c: Console = Console(style="green on black")


@click.command(name="print-default", help="Convenient defaults")
@click.option(
    "--configuration",
    is_flag=True,
    default=False,
    help="Prints out the default configuration for you to use",
)
@click.option(
    "--service",
    type=click.Choice(["systemd"]),
    help="Prints out a service file for the given init system to use",
)
@click.pass_context
def cli(
    ctx: click.Context,
    configuration: bool,
    service: str,
) -> None:
    if configuration:
        print(DEFAULT_FAN_CONFIG)
    elif service in SERVICES:
        print(SERVICES[service])
    else:
        print(ctx.get_help())
        sys.exit(1)


@click.command(
    name="manage",
    short_help="Run the controller",
    help="Run the controller in the foreground.\n\nThis command mostly exists for short-lived invocations on a manual shell. For more options and customization, consider using the *daemon* subcommand instead.",
)
def run_manager():
    FanController.start_manager(daemon=False)


class FileDescriptorOpt(click.ParamType):
    name = "fd"


@click.command(
    name="daemon",
    help="Run the controller as a service",
)
@click.option(
    "-f",
    "--notification-fd",
    type=FileDescriptorOpt(),
    help="Specify file descriptor for ready state",
)
@click.option(
    "--pidfile",
    "-p",
    type=click.Path(),
    default=os.path.join(PIDFILE_DIR, "amdfan.pid"),
    help="Pidfile path",
    show_default=True,
)
@click.option(
    "--no-pidfile",
    is_flag=True,
    help="Disable pidfile",
)
@click.option(
    "-l",
    "--logfile",
    type=click.Path(),
    default="/var/log/amdfan.log",
    help="Logging path",
    show_default=True,
)
@click.option(
    "--no-logfile",
    "--stdout",
    is_flag=True,
    help="Disable logging file (prints to stdout instead)",
)
@click.option(
    "-b",
    "--daemon",
    "--background",
    is_flag=True,
    help="Fork into the background as a daemon. Note that this detaches amdfan from your terminal.",
)
@click.option(
    "-s",
    "--signal",
    "action",
    type=click.Choice(["stop", "reload"]),
    default=None,
    help="Stop or reload a running instance from the given pidfile",
)
def run_daemon(
    notification_fd, logfile, pidfile, daemon, no_pidfile, no_logfile, action
):
    if no_pidfile:
        pidfile = None
    if no_logfile:
        logfile = None

    if action:
        try:
            with open(pidfile) as f:
                pid = int(f.read())
                if action == "stop":
                    os.kill(pid, signal.SIGTERM)
                elif action == "reload":
                    os.kill(pid, signal.SIGHUP)

        except FileNotFoundError:
            LOGGER.warning("Could not find pidfile=%s", pidfile)
        except ValueError:
            LOGGER.warning("Invalid PID value in pidfile=%s", pidfile)
    else:
        FanController.start_manager(
            notification_fd=notification_fd,
            pidfile=pidfile,
            logfile=logfile,
            daemon=daemon,
        )


def show_table(cards: Dict) -> Table:
    table = Table(title="amdgpu")
    table.add_column("Card")
    table.add_column("fan_speed (RPM)")
    table.add_column("gpu_temp ℃")
    for card, card_value in cards.items():
        table.add_row(f"{card}", f"{card_value.fan_speed}", f"{card_value.gpu_temp}")
    return table


@click.command(name="monitor", help="View the current temperature and speed")
@click.option("--fps", default=5, help="Updates per second", show_default=True)
@click.option("-1", "--single-run", is_flag=True, default=False, help="Print and exit")
def monitor_cards(fps, single_run) -> None:
    scanner = Scanner()
    if not single_run:
        c.print("AMD Fan Control - Ctrl-c to quit")

    with Live(refresh_per_second=fps) as live:
        while 1:
            live.update(show_table(scanner.cards))
            if single_run:
                return
            time.sleep(1 / fps)


class CardOpt(click.ParamType):
    name = "CARD"


class SpeedOpt(click.ParamType):
    name = "SPEED"


@click.command(
    name="set",
    short_help="Manually override the fan speed",
    help="Manually override the fan speed.\n\nIf insufficient properties are passed, goes into interactive mode. If both values are valid, interactive mode is not necessary\n\nSpeed values are set with integer values representing a percentage, and can be reverted back to the automatic controller by setting the speed to 'auto'.",
)
@click.option("--card", type=CardOpt(), help="Specify which card to override")
@click.option(
    "--speed",
    type=SpeedOpt(),
    help="Specify which speed to change to",
)
def set_fan_speed(card, speed) -> None:
    scanner = Scanner()
    if card is None:
        card_to_set = Prompt.ask("Which card?", choices=list(scanner.cards.keys()))
    else:
        card_to_set = card

    if speed is None:
        input_fan_speed = Prompt.ask("Fan speed, [1..100]% or 'auto'", default="auto")
    else:
        input_fan_speed = speed

    while True:
        if input_fan_speed.isdigit():
            if int(input_fan_speed) >= 1 and int(input_fan_speed) <= 100:
                LOGGER.debug("good %d", int(input_fan_speed))
                break
        elif input_fan_speed == "auto":
            LOGGER.debug("fan speed set to auto")
            break
        c.print("maybe try picking one of the options")

    selected_card = scanner.cards.get(card_to_set)
    if not selected_card:
        LOGGER.error("Found no card to set speed of")
    elif not input_fan_speed.isdigit() and input_fan_speed == "auto":
        LOGGER.info("Setting fan speed to system controlled")
        selected_card.set_system_controlled_fan(True)
    else:
        LOGGER.info("Setting fan speed to %d", int(input_fan_speed))
        c.print(selected_card.set_fan_speed(int(input_fan_speed)))


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
