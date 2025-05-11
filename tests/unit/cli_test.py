import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import requests
from click.testing import CliRunner
from intezer_sdk import errors as sdk_errors

import intezer_analyze_cli.key_store as key_store
from intezer_analyze_cli import cli


class CliSpec(unittest.TestCase):
    def setUp(self):
        super(CliSpec, self).setUp()
        self.runner = CliRunner()


class CliLoginSpec(CliSpec):
    def test_login_succeeded(self):
        # Arrange
        api_key = '123e4567-e89b-12d3-a456-426655440000'

        # Act
        with patch('intezer_analyze_cli.commands.login'):
            result = self.runner.invoke(cli.main_cli, [cli.login.name, api_key])
        # Assert
        self.assertEqual(result.exit_code, 0)

    def test_login_succeeded_with_url(self):
        # Arrange
        api_key = '123e4567-e89b-12d3-a456-426655440000'
        analyze_url = 'http://127.0.0.1'

        # Act
        with patch('intezer_analyze_cli.commands.login') as mock:
            result = self.runner.invoke(cli.main_cli, [cli.login.name, api_key, analyze_url])
            # Assert
            mock.assert_called_once_with(api_key, analyze_url + '/api/')

        self.assertEqual(result.exit_code, 0)

    def test_login_invalid_key(self):
        # Arrange
        api_key = '123e4567-e89b-12d3-a456-426655440000'

        # Act
        with patch('intezer_analyze_cli.cli.api.set_global_api',
                   side_effect=sdk_errors.InvalidApiKey(requests.Response())):
            result = self.runner.invoke(cli.main_cli, [cli.login.name, api_key])
        # Assert
        self.assertEqual(result.exit_code, 1)
        self.assertTrue(b'Invalid API key' in result.stdout_bytes)
        self.assertTrue(b'Aborted' in result.stdout_bytes)

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
        self.assertTrue(b'Cant find API key' in result.stdout_bytes)
        self.assertTrue(b'Aborted' in result.stdout_bytes)


class CliAnalyzeSpec(CliSpec):
    def setUp(self):
        super(CliAnalyzeSpec, self).setUp()

        create_global_api_patcher = patch('intezer_analyze_cli.commands.login')
        self.create_global_api_patcher_mock = create_global_api_patcher.start()
        self.addCleanup(create_global_api_patcher.stop)

        key_store.get_stored_api_key = MagicMock(return_value='api_key')

        create_analyze_file_command_patcher = patch('intezer_analyze_cli.commands.analyze_file_command')
        self.create_analyze_file_command_mock = create_analyze_file_command_patcher.start()
        self.addCleanup(create_analyze_file_command_patcher.stop)

    def test_analyze_file_with_no_unpacking_and_no_no_static_extraction(self):
        # Arrange
        file_path = __file__

        # Act
        result = self.runner.invoke(cli.main_cli,
                                    [cli.analyze.name,
                                     file_path,
                                     '--no-unpacking', '--no-static-extraction'])
        # Assert
        self.assertEqual(result.exit_code, 0, result.exception)
        self.assertTrue(self.create_analyze_file_command_mock.called)
        self.create_analyze_file_command_mock.assert_called_once_with(file_path=file_path,
                                                                      disable_dynamic_unpacking=True,
                                                                      disable_static_unpacking=True,
                                                                      code_item_type=None)

    def test_analyze_file(self):
        # Arrange
        file_path = __file__

        # Act
        result = self.runner.invoke(cli.main_cli, [cli.analyze.name, file_path])
        # Assert
        self.assertEqual(result.exit_code, 0, result.exception)
        self.assertTrue(self.create_analyze_file_command_mock.called)
        self.create_analyze_file_command_mock.assert_called_once_with(file_path=file_path,
                                                                      disable_dynamic_unpacking=None,
                                                                      disable_static_unpacking=None,
                                                                      code_item_type=None)

    def test_analyze_memory_module(self):
        # Arrange
        file_path = __file__

        # Act
        result = self.runner.invoke(cli.main_cli, [cli.analyze.name, '--code-item-type=file', file_path])
        # Assert
        self.assertEqual(result.exit_code, 0, result.exception)
        self.assertTrue(self.create_analyze_file_command_mock.called)
        self.create_analyze_file_command_mock.assert_called_once_with(file_path=file_path,
                                                                      disable_dynamic_unpacking=None,
                                                                      disable_static_unpacking=None,
                                                                      code_item_type='file')

    @patch('intezer_analyze_cli.commands.analyze_directory_command')
    def test_analyze_directory(self, create_analyze_directory_command_mock):
        # Arrange
        directory_path = os.path.dirname(__file__)

        # Act
        result = self.runner.invoke(cli.main_cli,
                                    [cli.analyze.name,
                                     directory_path])

        # Assert
        self.assertEqual(result.exit_code, 0, result.exception)
        self.assertTrue(create_analyze_directory_command_mock.called)
        create_analyze_directory_command_mock.assert_called_once_with(path=directory_path,
                                                                      disable_dynamic_unpacking=None,
                                                                      disable_static_unpacking=None,
                                                                      code_item_type=None,
                                                                      ignore_directory_count_limit=False)


class UploadOfflineEndpointScanSpec(CliSpec):
    def setUp(self):
        super(UploadOfflineEndpointScanSpec, self).setUp()

        create_global_api_patcher = patch('intezer_analyze_cli.cli.create_global_api')
        self.create_global_api_patcher_mock = create_global_api_patcher.start()
        self.addCleanup(create_global_api_patcher.stop)

        key_store.get_stored_api_key = MagicMock(return_value='api_key')

    @patch('intezer_analyze_cli.commands.upload_offline_endpoint_scan')
    def test_upload_offline_endpoint_scan(self, upload_offline_endpoint_scan):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            directory_path = os.path.join(temp_dir, 'offline_scan_directory')
            os.makedirs(directory_path)

            # Act
            result = self.runner.invoke(cli.main_cli,
                                        [cli.upload_endpoint_scan.name,
                                         directory_path])

            # Assert
            self.assertEqual(result.exit_code, 0, result.exception)
            self.assertTrue(upload_offline_endpoint_scan.called)
            upload_offline_endpoint_scan.assert_called_once_with(offline_scan_directory=directory_path,
                                                                 force=False,
                                                                 max_concurrent_uploads=0)

    @patch('intezer_analyze_cli.commands.upload_offline_endpoint_scan')
    def test_upload_offline_endpoint_scan_with_force(self, upload_offline_endpoint_scan):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            directory_path = os.path.join(temp_dir, 'offline_scan_directory')
            os.makedirs(directory_path)

            # Act
            result = self.runner.invoke(cli.main_cli,
                                        [cli.upload_endpoint_scan.name,
                                         directory_path, '--force'])

            # Assert
            self.assertEqual(result.exit_code, 0, result.exception)
            self.assertTrue(upload_offline_endpoint_scan.called)
            upload_offline_endpoint_scan.assert_called_once_with(offline_scan_directory=directory_path,
                                                                 force=True,
                                                                 max_concurrent_uploads=0)

    @patch('intezer_analyze_cli.commands.upload_multiple_offline_endpoint_scans')
    def test_upload_multiple_offline_endpoint_scans(self, upload_multiple_offline_endpoint_scans):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            directory_path = os.path.join(temp_dir, 'offline_scan_directory')
            os.makedirs(directory_path)
            # Act
            result = self.runner.invoke(cli.main_cli,
                                        [cli.upload_endpoint_scans_in_directory.name,
                                         directory_path])

            # Assert
            self.assertEqual(result.exit_code, 0, result.exception)
            self.assertTrue(upload_multiple_offline_endpoint_scans.called)
            upload_multiple_offline_endpoint_scans.assert_called_once_with(offline_scans_root_directory=directory_path,
                                                                           force=False,
                                                                           max_concurrent_uploads=0)

    @patch('intezer_analyze_cli.commands.upload_multiple_offline_endpoint_scans')
    def test_upload_multiple_offline_endpoint_scans_force(self, upload_multiple_offline_endpoint_scans):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Arrange
            directory_path = os.path.join(temp_dir, 'offline_scan_directory')
            os.makedirs(directory_path)

            # Act
            result = self.runner.invoke(cli.main_cli,
                                        [cli.upload_endpoint_scans_in_directory.name,
                                         directory_path, '--force'])

            # Assert
            self.assertEqual(result.exit_code, 0, result.exception)
            self.assertTrue(upload_multiple_offline_endpoint_scans.called)
            upload_multiple_offline_endpoint_scans.assert_called_once_with(offline_scans_root_directory=directory_path,
                                                                           force=True,
                                                                           max_concurrent_uploads=0)


class UploadPhishingSpec(CliSpec):
    @patch('intezer_analyze_cli.commands.send_phishing_emails_from_directory_command')
    def test_upload_multiple_eml_files(self, send_phishing_emails_from_directory_command):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            directory_path = os.path.join(temp_dir, 'eml_files_directory')
            os.makedirs(directory_path)
            # Act
            result = self.runner.invoke(cli.main_cli,
                                        [cli.upload_emails_in_directory.name,
                                         directory_path])

            # Assert
            self.assertEqual(result.exit_code, 0, result.exception)
            self.assertTrue(send_phishing_emails_from_directory_command.called)
            send_phishing_emails_from_directory_command.assert_called_once_with(path=directory_path,
                                                                                ignore_directory_count_limit=False)

    @patch('intezer_analyze_cli.commands.send_phishing_emails_from_directory_command')
    def test_upload_multiple_eml_files_ignore(self, send_phishing_emails_from_directory_command):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Arrange
            directory_path = os.path.join(temp_dir, 'eml_files_directory')
            os.makedirs(directory_path)

            # Act
            result = self.runner.invoke(cli.main_cli,
                                        [cli.upload_emails_in_directory.name,
                                         directory_path, '--ignore-directory-count-limit'])

            # Assert
            self.assertEqual(result.exit_code, 0, result.exception)
            self.assertTrue(send_phishing_emails_from_directory_command.called)
            send_phishing_emails_from_directory_command.assert_called_once_with(path=directory_path,
                                                                                ignore_directory_count_limit=True)


class CliIndexSpec(CliSpec):
    def setUp(self):
        super(CliIndexSpec, self).setUp()

        create_global_api_patcher = patch('intezer_analyze_cli.cli.create_global_api')
        self.create_global_api_patcher_mock = create_global_api_patcher.start()
        self.addCleanup(create_global_api_patcher.stop)

        key_store.get_stored_api_key = MagicMock(return_value='api_key')

    @patch('intezer_analyze_cli.commands.index_file_command')
    def test_index_file(self, create_index_file_command_mock):
        # Arrange
        file_path = __file__
        index_as = 'trusted'

        # Act
        result = self.runner.invoke(cli.main_cli, [cli.index.name, file_path, f'--index-as={index_as}'])

        # Assert
        self.assertEqual(result.exit_code, 0, result.exception)
        self.assertTrue(self.create_global_api_patcher_mock.called)
        create_index_file_command_mock.assert_called_once_with(file_path=file_path,
                                                               index_as=index_as,
                                                               family_name=None)

    @patch('intezer_analyze_cli.commands.index_directory_command')
    def test_index_directory(self, create_index_directory_command_mock):
        # Arrange
        directory_path = os.path.dirname(__file__)
        index_as = 'trusted'

        # Act
        result = self.runner.invoke(cli.main_cli, [cli.index.name, directory_path, f'--index-as={index_as}'])
        # Assert
        self.assertEqual(result.exit_code, 0, result.exception)
        self.assertTrue(self.create_global_api_patcher_mock.called)
        create_index_directory_command_mock.assert_called_once_with(directory_path=directory_path,
                                                                    index_as=index_as,
                                                                    family_name=None,
                                                                    ignore_directory_count_limit=False)

    def test_index_file_with_wrong_index_name_raise_error(self):
        # Arrange
        file_path = __file__
        index_as = 'wrong_index_name'

        # Act
        result = self.runner.invoke(cli.main_cli, [cli.index.name, file_path, '--index-as=wrong_index_name'])
        # Assert
        self.assertEqual(result.exit_code, 2, result.exception)
        self.assertTrue(b'Usage: main-cli index [OPTIONS] PATH [FAMILY_NAME]' in result.stdout_bytes)
        self.assertTrue(b'Try \'main-cli index -h\' for help.' in result.stdout_bytes)
        self.assertTrue(b'Error: Invalid value for \'--index-as\': invalid choice: wrong_index_name. '
                        b'(choose from malicious, trusted)' in result.stdout_bytes)

    @patch('intezer_analyze_cli.commands.index_by_txt_file_command')
    def test_index_by_txt_file_command(self, create_index_by_txt_file_command_mock):
        # Arrange
        dir_name = Path(__file__).parent.parent.absolute()
        file_path = os.path.join(dir_name, 'resources/test_hashes.txt')
        index_as = 'trusted'

        # Act
        result = self.runner.invoke(cli.main_cli, [cli.index_by_list.name, file_path, f'--index-as={index_as}'])

        # Assert
        self.assertEqual(result.exit_code, 0, result.exception)
        self.assertTrue(self.create_global_api_patcher_mock.called)
        create_index_by_txt_file_command_mock.assert_called_once_with(path=file_path,
                                                                      index_as=index_as,
                                                                      family_name=None)

    def test_index_by_txt_file_command_family_none(self):
        # Arrange
        dir_name = Path(__file__).parent.parent.absolute()
        file_path = os.path.join(dir_name, 'resources/test_hashes.txt')
        index_as = 'malicious'

        # Act
        result = self.runner.invoke(cli.main_cli, [cli.index_by_list.name, file_path, f'--index-as={index_as}'])

        # Assert
        self.assertEqual(result.exit_code, 0, result.exception)
        self.assertFalse(self.create_global_api_patcher_mock.called)

    def test_index_by_txt_file_command_wrong_index(self):
        # Arrange
        dir_name = Path(__file__).parent.parent.absolute()
        file_path = os.path.join(dir_name, 'resources/test_hashes.txt')
        index_as = 'wrong_index_name'

        # Act
        result = self.runner.invoke(cli.main_cli, [cli.index_by_list.name, file_path, f'--index-as={index_as}'])

        # Assert
        self.assertEqual(result.exit_code, 2, result.exception)
        self.assertTrue(b'Usage: main-cli index-by-list [OPTIONS] PATH [FAMILY_NAME]' in result.stdout_bytes)
        self.assertTrue(b'Try \'main-cli index-by-list -h\' for help.' in result.stdout_bytes)
        self.assertTrue(b'Error: Invalid value for \'--index-as\': invalid choice: wrong_index_name. '
                        b'(choose from malicious, trusted)' in result.stdout_bytes)
