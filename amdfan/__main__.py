#!/usr/bin/env python
"""entry point for amdfan"""
# __main__.py
import click

from .commands import cli, monitor_cards, run_daemon, run_manager, set_fan_speed


@click.group()
@click.version_option(None, "-v", "--version", prog_name="amdfan")
def main():
    pass


main.add_command(cli)
main.add_command(run_manager)
main.add_command(run_daemon)
main.add_command(monitor_cards)
main.add_command(set_fan_speed)

if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
