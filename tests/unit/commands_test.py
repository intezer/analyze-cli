import unittest

from click._compat import PY2
from click.testing import CliRunner

from intezer_analyze_cli import cli

if PY2:
    from mock import patch

else:
    from unittest.mock import patch


class CommandsSpec(unittest.TestCase):
    def setUp(self):
        super(CommandsSpec, self).setUp()
        self.runner = CliRunner()

    def test_login_succeeded(self):
        # Arrange
        api_key = '123e4567-e89b-12d3-a456-426655440000'

        # Act
        with patch('intezer_analyze_cli.commands.login'):
            result = self.runner.invoke(cli.main_cli,
                                        [cli.login.name,
                                         api_key])
        # Assert
        self.assertEqual(result.exit_code, 0)
