import unittest
import logging

from click.testing import CliRunner
from amdfan.amdfan import cli

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

class TestCli(unittest.TestCase):
    def test_params(self):
        daemon_param = "--daemon"
        runner = CliRunner()
        result = runner.invoke(cli, daemon_param)
        logger.debug(dir(result))
        assert result.exception
        assert result.exit_code == 1 # should be permission denied for non-root
        help_param = "--help"
        result = runner.invoke(cli, help_param)
        logger.debug(result.output)
        assert result.exit_code == 0
        manual_param = "--manual"
        result = runner.invoke(cli, manual_param, input='\n'.join(['card0', "25"]))
        logger.debug(result.output)
        assert result.exception
        assert result.exit_code == 1  # should be permission denied for non-root
