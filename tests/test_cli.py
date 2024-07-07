import unittest

from click.testing import CliRunner

from amdfan.commands import cli, run_daemon, set_fan_speed


class TestCli(unittest.TestCase):
    def test_params(self):
        runner = CliRunner()
        result = runner.invoke(run_daemon)
        assert result.exception
        assert result.exit_code == 1  # should be permission denied for non-root

        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

        result = runner.invoke(cli, ["--configuration"])
        assert result.exit_code == 0

        result = runner.invoke(cli, ["--service=systemd"])
        assert result.exit_code == 0

        result = runner.invoke(set_fan_speed, input="\n".join(["card0", "25"]))
        assert result.exception
        assert result.exit_code == 1  # should be permission denied for non-root
