#!/usr/bin/env python
""" entry point for amdfan """
# noqa: E501
import sys
import time
from typing import Dict

import click
from rich.console import Console
from rich.live import Live
from rich.prompt import Prompt
from rich.table import Table
from rich.traceback import install

from .config import LOGGER
from .controller import FanController, Scanner
from .defaults import DEFAULT_FAN_CONFIG, SERVICES

install()  # install traceback formatter

c: Console = Console(style="green on black")


@click.command()
@click.option(
    "--daemon", is_flag=True, default=False, help="Run as daemon applying the fan curve"
)
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
    daemon: bool,
    configuration: bool,
    service: bool,
) -> None:
    if daemon:
        FanController.start_daemon()
    elif configuration:
        print(DEFAULT_FAN_CONFIG)
    elif service in SERVICES:
        print(SERVICES[service])
    else:
        print(ctx.get_help())
        sys.exit(1)


def show_table(cards: Dict) -> Table:
    table = Table(title="amdgpu")
    table.add_column("Card")
    table.add_column("fan_speed (RPM)")
    table.add_column("gpu_temp ℃")
    for card, card_value in cards.items():
        table.add_row(f"{card}", f"{card_value.fan_speed}", f"{card_value.gpu_temp}")
    return table


@click.command()
@click.option(
    "--monitor",
    is_flag=True,
    default=False,
    help="Run as a monitor showing temp and fan speed",
)
def monitor_cards() -> None:
    c.print("AMD Fan Control - ctrl-c to quit")
    scanner = Scanner()
    with Live(refresh_per_second=4) as live:
        while 1:
            time.sleep(0.4)
            live.update(show_table(scanner.cards))


@click.command()
@click.option(
    "--manual",
    is_flag=True,
    default=False,
    help="Manually set the fan speed value of a card",
)
def set_fan_speed() -> None:
    scanner = Scanner()
    card_to_set = Prompt.ask("Which card?", choices=list(scanner.cards.keys()))
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
