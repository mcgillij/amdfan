import unittest

from click.testing import CliRunner

from amdfan.commands import cli


class TestCli(unittest.TestCase):
    def test_params(self):
        daemon_param = ["daemon"]
        runner = CliRunner()
        result = runner.invoke(cli, daemon_param)
        assert result.exception
        assert result.exit_code == 1  # should be permission denied for non-root

        help_param = ["--help"]
        result = runner.invoke(cli, help_param)
        assert result.exit_code == 0

        config_param = ["print-default", "--configuration"]
        result = runner.invoke(cli, config_param)
        assert result.exit_code == 0

        service_param = ["print-default", "--service=systemd"]
        result = runner.invoke(cli, service_param)
        assert result.exit_code == 0

        manual_param = "set"
        result = runner.invoke(cli, manual_param, input="\n".join(["card0", "25"]))
        assert result.exception
        assert result.exit_code == 1  # should be permission denied for non-root
