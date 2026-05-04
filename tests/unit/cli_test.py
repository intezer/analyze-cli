import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY
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


class AlertsSpec(CliSpec):
    def setUp(self):
        super(AlertsSpec, self).setUp()

        create_global_api_patcher = patch('intezer_analyze_cli.cli.create_global_api')
        self.create_global_api_patcher_mock = create_global_api_patcher.start()
        self.addCleanup(create_global_api_patcher.stop)

        key_store.get_stored_api_key = MagicMock(return_value='api_key')

    @patch('intezer_analyze_cli.commands.notify_alerts_from_csv_command')
    def test_alerts_notify_from_csv_success(self, notify_alerts_from_csv_command_mock):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_file_path = os.path.join(temp_dir, 'alerts.csv')
            with open(csv_file_path, 'w') as f:
                f.write('id,environment\ntest-alert-1,production\ntest-alert-2,staging\n')

            # Act
            result = self.runner.invoke(cli.main_cli,
                                        ['alerts', 'notify-from-csv', csv_file_path])

            # Assert
            self.assertEqual(result.exit_code, 0, result.exception)
            self.assertTrue(notify_alerts_from_csv_command_mock.called)
            notify_alerts_from_csv_command_mock.assert_called_once_with(csv_path=csv_file_path)

    def test_alerts_notify_from_csv_file_not_exists_returns_error(self):
        # Arrange
        non_existent_file = '/non/existent/file.csv'

        # Act
        result = self.runner.invoke(cli.main_cli,
                                    ['alerts', 'notify-from-csv', non_existent_file])

        # Assert
        self.assertEqual(result.exit_code, 2)
        self.assertTrue(b'does not exist' in result.stdout_bytes)

class SubtenantCliSpec(CliSpec):
    def setUp(self):
        super(SubtenantCliSpec, self).setUp()

        create_global_api_patcher = patch('intezer_analyze_cli.cli.create_global_api')
        self.create_global_api_patcher_mock = create_global_api_patcher.start()
        self.addCleanup(create_global_api_patcher.stop)

        key_store.get_stored_api_key = MagicMock(return_value='api_key')

    @patch('intezer_analyze_cli.subtenant_commands.upload_subtenants_from_csv_command')
    def test_subtenant_upload_from_csv_success(self, upload_mock):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_file_path = os.path.join(temp_dir, 'subtenants.csv')
            with open(csv_file_path, 'w') as f:
                f.write('Tenant name,Accounts,Sites\nTestTenant,Acct1,Site1\n')

            # Act
            result = self.runner.invoke(cli.main_cli,
                                        ['subtenant', 'upload-from-csv', csv_file_path])

            # Assert
            self.assertEqual(result.exit_code, 0, result.exception)
            self.assertTrue(upload_mock.called)
            upload_mock.assert_called_once_with(csv_path=csv_file_path, skip_dedup=False)

    @patch('intezer_analyze_cli.subtenant_commands.upload_subtenants_from_csv_command')
    def test_subtenant_upload_from_csv_with_skip_dedup(self, upload_mock):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_file_path = os.path.join(temp_dir, 'subtenants.csv')
            with open(csv_file_path, 'w') as f:
                f.write('Tenant name\nTestTenant\n')

            # Act
            result = self.runner.invoke(cli.main_cli,
                                        ['subtenant', 'upload-from-csv', csv_file_path, '--skip-dedup'])

            # Assert
            self.assertEqual(result.exit_code, 0, result.exception)
            upload_mock.assert_called_once_with(csv_path=csv_file_path, skip_dedup=True)

    def test_subtenant_upload_from_csv_file_not_exists_returns_error(self):
        # Act
        result = self.runner.invoke(cli.main_cli,
                                    ['subtenant', 'upload-from-csv', '/non/existent/file.csv'])

        # Assert
        self.assertEqual(result.exit_code, 2)
        self.assertTrue(b'does not exist' in result.stdout_bytes)

    def test_subtenant_group_help_shows_subcommands(self):
        # Act
        result = self.runner.invoke(cli.main_cli, ['subtenant', '--help'])

        # Assert
        self.assertEqual(result.exit_code, 0)
        self.assertIn(b'upload-from-csv', result.stdout_bytes)


class AlertsDataSourcesCliSpec(CliSpec):
    def setUp(self):
        super(AlertsDataSourcesCliSpec, self).setUp()

        create_global_api_patcher = patch('intezer_analyze_cli.cli.create_global_api')
        self.create_global_api_patcher_mock = create_global_api_patcher.start()
        self.addCleanup(create_global_api_patcher.stop)

        key_store.get_stored_api_key = MagicMock(return_value='api_key')

    @patch('intezer_analyze_cli.connector_commands.connect_alert_data_source_command')
    def test_connect_invokes_command_with_correct_args(self, connect_mock):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'creds.json')
            with open(config_path, 'w') as f:
                json.dump({'crowdstrike': {'client_id': 'id'}}, f)

            # Act
            result = self.runner.invoke(cli.main_cli, [
                'alerts-data-sources', 'connect',
                '--source', 'crowdstrike',
                '--name', 'acme-corp',
                '--config', config_path,
                '--resolve-false-positive',
                '--noting',
                '--auto-endpoint-scan',
                '--wait'
            ])

            # Assert
            self.assertEqual(result.exit_code, 0, result.exception)
            connect_mock.assert_called_once_with(
                source='crowdstrike',
                name='acme-corp',
                config_file=ANY,
                resolve_false_positive=True,
                noting=True,
                auto_endpoint_scan=True,
                wait=True
            )

    @patch('intezer_analyze_cli.connector_commands.connect_alert_data_source_command')
    def test_connect_invokes_command_with_defaults(self, connect_mock):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'creds.json')
            with open(config_path, 'w') as f:
                json.dump({}, f)

            # Act
            result = self.runner.invoke(cli.main_cli, [
                'alerts-data-sources', 'connect',
                '--source', 'crowdstrike',
                '--name', 'acme-corp',
                '--config', config_path
            ])

            # Assert
            self.assertEqual(result.exit_code, 0, result.exception)
            connect_mock.assert_called_once_with(
                source='crowdstrike',
                name='acme-corp',
                config_file=ANY,
                resolve_false_positive=False,
                noting=False,
                auto_endpoint_scan=False,
                wait=False
            )

    def test_connect_missing_required_source_returns_error(self):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'creds.json')
            with open(config_path, 'w') as f:
                json.dump({}, f)

            # Act
            result = self.runner.invoke(cli.main_cli, [
                'alerts-data-sources', 'connect',
                '--name', 'acme-corp',
                '--config', config_path
            ])

            # Assert
            self.assertEqual(result.exit_code, 2)
            self.assertIn(b'--source', result.stdout_bytes)

    def test_connect_missing_required_name_returns_error(self):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'creds.json')
            with open(config_path, 'w') as f:
                json.dump({}, f)

            # Act
            result = self.runner.invoke(cli.main_cli, [
                'alerts-data-sources', 'connect',
                '--source', 'crowdstrike',
                '--config', config_path
            ])

            # Assert
            self.assertEqual(result.exit_code, 2)
            self.assertIn(b'--name', result.stdout_bytes)

    @patch('intezer_analyze_cli.connector_commands.connect_alert_data_sources_batch_command')
    def test_connect_batch_invokes_command_with_defaults(self, batch_mock):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'connectors.jsonl')
            entries = [
                {'alert_source': 'crowdstrike', 'connector_name': 'acme-cs',
                 'crowdstrike': {'client_id': 'a', 'client_secret': 'b'}},
                {'alert_source': 'sentinel_one', 'connector_name': 'acme-s1',
                 'sentinel_one': {'api_token': 't', 'base_url': 'https://example'}},
            ]
            with open(config_path, 'w') as f:
                f.write('\n'.join(json.dumps(e) for e in entries))

            # Act
            result = self.runner.invoke(cli.main_cli, [
                'alerts-data-sources', 'connect-batch',
                '--config', config_path,
            ])

            # Assert
            self.assertEqual(result.exit_code, 0, result.exception)
            batch_mock.assert_called_once_with(
                config_file=ANY,
                wait=False,
                max_concurrent=5,
            )

    @patch('intezer_analyze_cli.connector_commands.connect_alert_data_sources_batch_command')
    def test_connect_batch_passes_through_flags(self, batch_mock):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'connectors.jsonl')
            with open(config_path, 'w') as f:
                f.write('{"alert_source":"crowdstrike","connector_name":"acme-cs"}\n')

            # Act
            result = self.runner.invoke(cli.main_cli, [
                'alerts-data-sources', 'connect-batch',
                '--config', config_path,
                '--wait',
                '--max-concurrent', '3',
            ])

            # Assert
            self.assertEqual(result.exit_code, 0, result.exception)
            batch_mock.assert_called_once_with(
                config_file=ANY,
                wait=True,
                max_concurrent=3,
            )

    def test_connect_batch_missing_required_config_returns_error(self):
        # Act
        result = self.runner.invoke(cli.main_cli, [
            'alerts-data-sources', 'connect-batch',
        ])

        # Assert
        self.assertEqual(result.exit_code, 2)
        self.assertIn(b'--config', result.stdout_bytes)

    def test_connect_batch_rejects_zero_concurrency(self):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'connectors.jsonl')
            with open(config_path, 'w') as f:
                f.write('{"alert_source":"crowdstrike","connector_name":"acme-cs"}\n')

            # Act
            result = self.runner.invoke(cli.main_cli, [
                'alerts-data-sources', 'connect-batch',
                '--config', config_path,
                '--max-concurrent', '0',
            ])

            # Assert
            self.assertEqual(result.exit_code, 2)
            self.assertIn(b'--max-concurrent', result.stdout_bytes)

    def test_connect_batch_rejects_concurrency_above_five(self):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'connectors.jsonl')
            with open(config_path, 'w') as f:
                f.write('{"alert_source":"crowdstrike","connector_name":"acme-cs"}\n')

            # Act
            result = self.runner.invoke(cli.main_cli, [
                'alerts-data-sources', 'connect-batch',
                '--config', config_path,
                '--max-concurrent', '6',
            ])

            # Assert
            self.assertEqual(result.exit_code, 2)
            self.assertIn(b'--max-concurrent', result.stdout_bytes)

    def test_connect_missing_required_config_returns_error(self):
        # Act
        result = self.runner.invoke(cli.main_cli, [
            'alerts-data-sources', 'connect',
            '--source', 'crowdstrike',
            '--name', 'acme-corp'
        ])

        # Assert
        self.assertEqual(result.exit_code, 2)
        self.assertIn(b'--config', result.stdout_bytes)

    @patch('intezer_analyze_cli.connector_commands.deactivate_alert_data_source_command')
    def test_deactivate_invokes_command_with_correct_args(self, deactivate_mock):
        # Act
        result = self.runner.invoke(cli.main_cli, [
            'alerts-data-sources', 'deactivate', 'acme-corp', '--wait'
        ])

        # Assert
        self.assertEqual(result.exit_code, 0, result.exception)
        deactivate_mock.assert_called_once_with(connector_id='acme-corp', wait=True)

    @patch('intezer_analyze_cli.connector_commands.deactivate_alert_data_source_command')
    def test_deactivate_invokes_command_without_wait(self, deactivate_mock):
        # Act
        result = self.runner.invoke(cli.main_cli, [
            'alerts-data-sources', 'deactivate', 'acme-corp'
        ])

        # Assert
        self.assertEqual(result.exit_code, 0, result.exception)
        deactivate_mock.assert_called_once_with(connector_id='acme-corp', wait=False)

    def test_deactivate_missing_connector_name_returns_error(self):
        # Act
        result = self.runner.invoke(cli.main_cli, [
            'alerts-data-sources', 'deactivate'
        ])

        # Assert
        self.assertEqual(result.exit_code, 2)

    @patch('intezer_analyze_cli.connector_commands.reactivate_alert_data_source_command')
    def test_activate_invokes_command_with_correct_args(self, activate_mock):
        # Act
        result = self.runner.invoke(cli.main_cli, [
            'alerts-data-sources', 'reactivate', 'acme-corp', '--wait'
        ])

        # Assert
        self.assertEqual(result.exit_code, 0, result.exception)
        activate_mock.assert_called_once_with(connector_id='acme-corp', wait=True)

    @patch('intezer_analyze_cli.connector_commands.update_alert_data_source_command')
    def test_update_invokes_command_with_correct_args(self, update_mock):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'new-creds.json')
            with open(config_path, 'w') as f:
                json.dump({'new_key': 'new_value'}, f)

            # Act
            result = self.runner.invoke(cli.main_cli, [
                'alerts-data-sources', 'update', 'acme-corp',
                '--config', config_path, '--wait'
            ])

            # Assert
            self.assertEqual(result.exit_code, 0, result.exception)
            update_mock.assert_called_once_with(
                connector_id='acme-corp',
                config_file=ANY,
                wait=True
            )

    def test_update_missing_required_config_returns_error(self):
        # Act
        result = self.runner.invoke(cli.main_cli, [
            'alerts-data-sources', 'update', 'acme-corp'
        ])

        # Assert
        self.assertEqual(result.exit_code, 2)
        self.assertIn(b'--config', result.stdout_bytes)

    @patch('intezer_analyze_cli.connector_commands.connect_alert_data_source_command')
    def test_group_accessible_with_underscores(self, connect_mock):
        # Arrange
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'creds.json')
            with open(config_path, 'w') as f:
                json.dump({}, f)

            # Act
            result = self.runner.invoke(cli.main_cli, [
                'alerts_data_sources', 'connect',
                '--source', 'crowdstrike',
                '--name', 'acme-corp',
                '--config', config_path
            ])

            # Assert
            self.assertEqual(result.exit_code, 0, result.exception)
            self.assertTrue(connect_mock.called)

    def test_group_help_shows_subcommands(self):
        # Act
        result = self.runner.invoke(cli.main_cli, ['alerts-data-sources', '--help'])

        # Assert
        self.assertEqual(result.exit_code, 0)
        self.assertIn(b'connect', result.stdout_bytes)
        self.assertIn(b'deactivate', result.stdout_bytes)
        self.assertIn(b'activate', result.stdout_bytes)
        self.assertIn(b'update', result.stdout_bytes)

    def test_connect_help_shows_options(self):
        # Act
        result = self.runner.invoke(cli.main_cli, ['alerts-data-sources', 'connect', '--help'])

        # Assert
        self.assertEqual(result.exit_code, 0)
        self.assertIn(b'--source', result.stdout_bytes)
        self.assertIn(b'--name', result.stdout_bytes)
        self.assertIn(b'--config', result.stdout_bytes)
        self.assertIn(b'--resolve-false-positive', result.stdout_bytes)
        self.assertIn(b'--noting', result.stdout_bytes)
        self.assertIn(b'--auto-endpoint-scan', result.stdout_bytes)
        self.assertIn(b'--wait', result.stdout_bytes)


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
