import os
import unittest

from click._compat import PY2
from click.testing import CliRunner
from intezer_sdk import errors as sdk_errors

from intezer_analyze_cli import cli

if PY2:
    from mock import patch

else:
    from unittest.mock import patch


class CliSpec(unittest.TestCase):
    def setUp(self):
        super(CliSpec, self).setUp()
        self.runner = CliRunner()


class CliLoginSpec(CliSpec):
    def setUp(self):
        super(CliLoginSpec, self).setUp()

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

    def test_login_invalid_key(self):
        # Arrange
        api_key = '123e4567-e89b-12d3-a456-426655440000'

        # Act
        with patch('intezer_analyze_cli.cli.api.set_global_api', side_effect=sdk_errors.InvalidApiKey):
            result = self.runner.invoke(cli.main_cli,
                                        [cli.login.name,
                                         api_key])
        # Assert
        self.assertEqual(result.exit_code, 1)
        self.assertTrue(b'Invalid API key' in result.output_bytes)
        self.assertTrue(b'Aborted' in result.output_bytes)

    def test_analyze_exits_when_not_login(self):
        # Arrange
        file_path = __file__

        with patch('intezer_analyze_cli.cli.key_store.get_stored_key', return_value=None):
            # Act
            result = self.runner.invoke(cli.main_cli,
                                        [cli.analyze.name,
                                         file_path])
        # Assert
        self.assertEqual(result.exit_code, 1)
        self.assertTrue(b'Cant find API key' in result.output_bytes)
        self.assertTrue(b'Aborted' in result.output_bytes)


class CliAnalyzeSpec(CliSpec):
    def setUp(self):
        super(CliAnalyzeSpec, self).setUp()

        create_global_api_patcher = patch('intezer_analyze_cli.commands.login')
        self.create_global_api_patcher_mock = create_global_api_patcher.start()
        self.addCleanup(create_global_api_patcher.stop)

        create_analyze_file_command_patcher = patch('intezer_analyze_cli.commands.analyze_file_command')
        self.create_analyze_file_command_mock = create_analyze_file_command_patcher.start()
        self.addCleanup(create_analyze_file_command_patcher.stop)

        create_analyze_analyze_directory_command_patcher = patch(
            'intezer_analyze_cli.commands.analyze_directory_command')
        self.create_analyze_directory_command_mock = create_analyze_analyze_directory_command_patcher.start()
        self.addCleanup(create_analyze_analyze_directory_command_patcher.stop)

    def test_analyze_file_with_anonymize_raise_error(self):
        # Arrange
        file_path = __file__

        # Act
        result = self.runner.invoke(cli.main_cli,
                                    [cli.analyze.name,
                                     file_path,
                                     '--anonymize'])
        # Assert
        self.assertEqual(result.exit_code, 1)

    def test_analyze_file_with_no_unpacking_and_no_no_static_extraction(self):
        # Arrange
        file_path = __file__

        # Act
        result = self.runner.invoke(cli.main_cli,
                                    [cli.analyze.name,
                                     file_path,
                                     '--no-unpacking', '--no-static-extraction'])
        # Assert
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(self.create_analyze_file_command_mock.called)
        self.create_analyze_file_command_mock.assert_called_once_with(file_path=file_path,
                                                                      no_unpacking=True,
                                                                      no_static_unpacking=True)

    def test_analyze_file(self):
        # Arrange
        file_path = __file__

        # Act
        result = self.runner.invoke(cli.main_cli,
                                    [cli.analyze.name,
                                     file_path])
        # Assert
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(self.create_analyze_file_command_mock.called)
        self.create_analyze_file_command_mock.assert_called_once_with(file_path=file_path,
                                                                      no_unpacking=False,
                                                                      no_static_unpacking=False)

    def test_analyze_directory(self):
        # Arrange
        directory_path = os.path.dirname(__file__)

        # Act
        result = self.runner.invoke(cli.main_cli,
                                    [cli.analyze.name,
                                     directory_path])
        # Assert
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(self.create_analyze_directory_command_mock.called)
        self.create_analyze_directory_command_mock.assert_called_once_with(path=directory_path,
                                                                           no_unpacking=False,
                                                                           no_static_unpacking=False)


class CliIndexSpec(CliSpec):
    def setUp(self):
        super(CliIndexSpec, self).setUp()

        create_global_api_patcher = patch('intezer_analyze_cli.cli.create_global_api')
        self.create_global_api_patcher_mock = create_global_api_patcher.start()
        self.addCleanup(create_global_api_patcher.stop)

        create_index_file_command_patcher = patch('intezer_analyze_cli.commands.index_file_command')
        self.create_index_file_command_mock = create_index_file_command_patcher.start()
        self.addCleanup(create_index_file_command_patcher.stop)

    def test_index_file(self):
        # Arrange
        file_path = __file__
        index_as = 'trusted'

        # Act
        result = self.runner.invoke(cli.main_cli,
                                    [cli.index.name,
                                     file_path, index_as])
        # Assert
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(self.create_global_api_patcher_mock.called)
        self.create_index_file_command_mock.assert_called_once_with(file_path=file_path,
                                                                    index_as=index_as,
                                                                    family_name=None)

    def test_index_file_with_wrong_index_name_raise_error(self):
        # Arrange
        file_path = __file__
        index_as = 'wrong_index_name'

        # Act
        result = self.runner.invoke(cli.main_cli,
                                    [cli.index.name,
                                     file_path, index_as])
        # Assert
        self.assertEqual(result.exit_code, 1)
        self.assertTrue(b'Index type can be trusted or malicious' in result.output_bytes)
