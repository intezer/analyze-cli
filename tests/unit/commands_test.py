import io
import json
import os
import tempfile
import unittest.mock
import uuid
from pathlib import Path
from tempfile import tempdir
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

import click.exceptions
import intezer_sdk.endpoint_analysis
import intezer_sdk.base_analysis
from intezer_sdk import errors as sdk_errors
import intezer_analyze_cli.key_store as key_store
from intezer_analyze_cli import commands
from intezer_analyze_cli import connector_commands
from intezer_analyze_cli.cli import create_global_api
from tests.unit.cli_test import CliSpec


class CommandsAnalyzeSpec(CliSpec):
    def setUp(self):
        super(CommandsAnalyzeSpec, self).setUp()

        create_global_api_patcher = patch('intezer_analyze_cli.commands.login')
        self.create_global_api_patcher_mock = create_global_api_patcher.start()
        self.addCleanup(create_global_api_patcher.stop)

        key_store.get_stored_api_key = MagicMock(return_value='api_key')

        send_analyze_patcher = patch('intezer_sdk.analysis.FileAnalysis.send')
        self.send_analyze_mock = send_analyze_patcher.start()
        self.addCleanup(send_analyze_patcher.stop)

    def test_analyze_exec_file(self):
        # Arrange
        create_global_api()
        file_path = __file__

        # Act
        commands.analyze_file_command(file_path, None, None, 'file')

        # Assert
        self.send_analyze_mock.assert_called_once()

    def test_analyze_none_exec_file_dynamic_param_empty(self):
        # Arrange
        create_global_api()
        dir_name = Path(__file__).parent.parent.absolute()
        file_path = os.path.join(dir_name, 'resources/doc_sample_file.doc')

        # Act
        commands.analyze_file_command(file_path, None, None, 'file')

        # Assert
        self.send_analyze_mock.assert_called_once()

    def test_analyze_none_exec_file_dynamic_enabled(self):
        # Arrange
        create_global_api()
        dir_name = Path(__file__).parent.parent.absolute()
        file_path = os.path.join(dir_name, 'resources/doc_sample_file.doc')

        # Act
        commands.analyze_file_command(file_path, False, None, 'file')

        # Assert
        self.send_analyze_mock.assert_called_once()

    def test_analyze_none_exec_file_dynamic_disabled(self):
        # Arrange
        create_global_api()
        dir_name = Path(__file__).parent.parent.absolute()
        file_path = os.path.join(dir_name, 'resources/doc_sample_file.doc')

        # Act
        commands.analyze_file_command(file_path, True, None, 'file')

        # Assert
        self.send_analyze_mock.assert_not_called()

class CommandEndpointAnalysisSpec(CliSpec):
    def setUp(self):
        super(CommandEndpointAnalysisSpec, self).setUp()

        create_global_api_patcher = patch('intezer_analyze_cli.commands.login')
        self.create_global_api_patcher_mock = create_global_api_patcher.start()
        self.addCleanup(create_global_api_patcher.stop)

        key_store.get_stored_api_key = MagicMock(return_value='api_key')

        send_analyze_patcher = patch('intezer_sdk.endpoint_analysis.EndpointAnalysis.send')
        self.send_analyze_mock = send_analyze_patcher.start()
        self.addCleanup(send_analyze_patcher.stop)

        analysis_id_patcher  = patch('intezer_sdk.endpoint_analysis.EndpointAnalysis.analysis_id', create=True, new_callable=unittest.mock.PropertyMock, return_value=str(uuid.uuid4()))
        self.analysis_id_mock = analysis_id_patcher.start()
        self.addCleanup(analysis_id_patcher.stop)

    @staticmethod
    def _create_temporary_directory_hierarchy(root):
        offline_scan_directory = os.path.join(root, 'offline_scan_directory')
        files_directory = os.path.join(root, 'files')
        fileless_directory = os.path.join(root, 'fileless')
        memory_modules_directory = os.path.join(root, 'memory_modules')
        os.makedirs(offline_scan_directory)
        os.makedirs(files_directory)
        os.makedirs(fileless_directory)
        os.makedirs(memory_modules_directory)
        return offline_scan_directory

    def test_offline_scan_upload(self):
        # Arrange
        create_global_api()
        with tempfile.TemporaryDirectory() as root:
            offline_scan_directory = self._create_temporary_directory_hierarchy(root)
            analysis_id_file_path = os.path.join(offline_scan_directory, 'analysis_id.txt')

            # Act
            commands.upload_offline_endpoint_scan(offline_scan_directory)

            # Assert
            self.send_analyze_mock.assert_called_once()
            self.assertTrue(os.path.isfile(analysis_id_file_path))

    def test_offline_scan_do_not_upload_if_already_uploaded(self):
        # Arrange
        create_global_api()
        with tempfile.TemporaryDirectory() as root:
            offline_scan_directory = self._create_temporary_directory_hierarchy(root)
            analysis_id_file_path = os.path.join(offline_scan_directory, 'analysis_id.txt')
            with open(analysis_id_file_path, 'w') as f:
                f.write(str(uuid.uuid4()))

            # Act and Assert
            with self.assertRaises(click.exceptions.Abort):
                commands.upload_offline_endpoint_scan(offline_scan_directory)

    def test_offline_scan_upload_if_already_uploaded_but_force(self):
        # Arrange
        create_global_api()
        with tempfile.TemporaryDirectory() as root:
            offline_scan_directory = self._create_temporary_directory_hierarchy(root)
            analysis_id_file_path = os.path.join(offline_scan_directory, 'analysis_id.txt')
            with open(analysis_id_file_path, 'w') as f:
                f.write(str(uuid.uuid4()))

            # Act
            commands.upload_offline_endpoint_scan(offline_scan_directory, force=True)

            # Assert
            self.send_analyze_mock.assert_called_once()
            self.assertTrue(os.path.isfile(analysis_id_file_path))

            # Assert that the analysis id file was overwritten with the new analysis id
            with open(analysis_id_file_path) as f:
                self.assertEqual(f.read(), self.analysis_id_mock.return_value)


    def test_offline_scan_upload_multiple(self):
        # Arrange
        create_global_api()
        with tempfile.TemporaryDirectory() as root:
            offline_scan_directory = self._create_temporary_directory_hierarchy(root)
            another_offline_scan_directory = os.path.join(root, 'another_offline_scan_directory')
            os.makedirs(another_offline_scan_directory)

            # Act
            commands.upload_multiple_offline_endpoint_scans(root)

            # Assert
            self.assertTrue(self.send_analyze_mock.call_count == 2)

    def test_offline_scan_upload_multiple_but_some_were_sent(self):
        # Arrange
        create_global_api()
        with tempfile.TemporaryDirectory() as root:
            offline_scan_directory1 = self._create_temporary_directory_hierarchy(root)
            offline_scan_directory2 = os.path.join(root, 'offline_scan_directory2')
            os.makedirs(offline_scan_directory2)
            offline_scan_directory3 = os.path.join(root, 'offline_scan_directory3')
            os.makedirs(offline_scan_directory3)
            offline_scan_directory4 = os.path.join(root, 'offline_scan_directory4')
            os.makedirs(offline_scan_directory4)
            offline_scan_directory5 = os.path.join(root, 'offline_scan_directory5')
            os.makedirs(offline_scan_directory5)

            analysis_id_file_path1 = os.path.join(offline_scan_directory1, 'analysis_id.txt')
            with open(analysis_id_file_path1, 'w') as f:
                f.write(str(uuid.uuid4()))

            analysis_id_file_path3 = os.path.join(offline_scan_directory3, 'analysis_id.txt')
            with open(analysis_id_file_path3, 'w') as f:
                f.write(str(uuid.uuid4()))

            # Act
            commands.upload_multiple_offline_endpoint_scans(root)

            # Assert
            self.assertTrue(self.send_analyze_mock.call_count == 3)


class CommandUploadPhishingSpec(CliSpec):
    def setUp(self):
        super(CommandUploadPhishingSpec, self).setUp()

        create_global_api_patcher = patch('intezer_analyze_cli.commands.login')
        self.create_global_api_patcher_mock = create_global_api_patcher.start()
        self.addCleanup(create_global_api_patcher.stop)

        key_store.get_stored_api_key = MagicMock(return_value='api_key')

        send_phishing_patcher = patch('intezer_sdk.alerts.Alert.send_phishing_email')
        self.send_phishing_mock = send_phishing_patcher.start()
        self.addCleanup(send_phishing_patcher.stop)

    def test_send_emal_files_from_directory(self):
        # Arrange
        create_global_api()
        dir_name = Path(__file__).parent.parent.absolute()
        file_path = os.path.join(dir_name, 'resources/emails_directory')

        # Act
        commands.send_phishing_emails_from_directory_command(file_path, True)

        # Assert
        self.assertEqual(self.send_phishing_mock.call_count, 2)


class CommandAlertsSpec(CliSpec):
    def setUp(self):
        super(CommandAlertsSpec, self).setUp()

        create_global_api_patcher = patch('intezer_analyze_cli.commands.login')
        self.create_global_api_patcher_mock = create_global_api_patcher.start()
        self.addCleanup(create_global_api_patcher.stop)

        key_store.get_stored_api_key = MagicMock(return_value='api_key')

    def test_notify_alerts_from_csv_command_handles_invalid_csv_no_id_column(self):
        # Arrange
        create_global_api()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_file_path = os.path.join(temp_dir, 'test_alerts_no_id.csv')
            with open(csv_file_path, 'w') as f:
                f.write('alert_id,environment\ntest-alert-1,production\n')

            # Act & Assert
            with patch('click.echo') as mock_echo:
                with self.assertRaises(click.exceptions.Abort):
                    commands.notify_alerts_from_csv_command(csv_file_path)
                
                mock_echo.assert_any_call('Unexpected error occurred while processing CSV file')

    def test_notify_alerts_from_csv_command_handles_empty_csv_file(self):
        # Arrange
        create_global_api()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_file_path = os.path.join(temp_dir, 'test_alerts_empty.csv')
            with open(csv_file_path, 'w') as f:
                f.write('id,environment\n')  # Only header, no data

            # Act & Assert
            with patch('click.echo') as mock_echo:
                with self.assertRaises(click.exceptions.Abort):
                    commands.notify_alerts_from_csv_command(csv_file_path)
                
                mock_echo.assert_any_call('Unexpected error occurred while processing CSV file')

    @patch('intezer_analyze_cli.commands.Alert')
    @patch('click.progressbar')
    def test_notify_alerts_from_csv_command_success(self, mock_progressbar, mock_alert_class):
        # Arrange
        create_global_api()
        
        # Mock progress bar
        mock_progress_context = MagicMock()
        mock_progressbar.return_value.__enter__.return_value = mock_progress_context
        
        # Mock Alert instances
        mock_alert1 = MagicMock()
        mock_alert1.notify.return_value = ['email', 'slack']
        mock_alert2 = MagicMock()
        mock_alert2.notify.return_value = ['email']
        mock_alert_class.side_effect = [mock_alert1, mock_alert2]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_file_path = os.path.join(temp_dir, 'test_alerts.csv')
            with open(csv_file_path, 'w') as f:
                f.write('id,environment\ntest-alert-1,production\ntest-alert-2,staging\n')

            # Act
            with patch('click.echo') as mock_echo:
                commands.notify_alerts_from_csv_command(csv_file_path)

            # Assert
            self.assertEqual(mock_alert_class.call_count, 2)
            mock_alert_class.assert_any_call(alert_id='test-alert-1', environment='production')
            mock_alert_class.assert_any_call(alert_id='test-alert-2', environment='staging')
            
            mock_alert1.notify.assert_called_once()
            mock_alert2.notify.assert_called_once()
            
            # Check that success message was printed
            mock_echo.assert_any_call('2 alerts notified successfully')

    @patch('intezer_analyze_cli.commands.Alert')
    @patch('click.progressbar')
    def test_notify_alerts_from_csv_command_handles_no_channels(self, mock_progressbar, mock_alert_class):
        # Arrange
        create_global_api()
        
        # Mock progress bar
        mock_progress_context = MagicMock()
        mock_progressbar.return_value.__enter__.return_value = mock_progress_context
        
        # Mock Alert instance with no channels
        mock_alert = MagicMock()
        mock_alert.notify.return_value = []  # No channels configured
        mock_alert_class.return_value = mock_alert
        
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_file_path = os.path.join(temp_dir, 'test_alerts.csv')
            with open(csv_file_path, 'w') as f:
                f.write('id,environment\ntest-alert-1,production\n')

            # Act
            with patch('click.echo') as mock_echo:
                commands.notify_alerts_from_csv_command(csv_file_path)

            # Assert
            mock_alert.notify.assert_called_once()
            mock_echo.assert_any_call('1 alerts didn\'t triggered any notification')

    @patch('intezer_analyze_cli.commands.Alert')
    @patch('click.progressbar')
    def test_notify_alerts_from_csv_command_handles_alert_not_found(self, mock_progressbar, mock_alert_class):
        # Arrange
        create_global_api()
        
        # Mock progress bar
        mock_progress_context = MagicMock()
        mock_progressbar.return_value.__enter__.return_value = mock_progress_context
        
        # Mock Alert instance that raises AlertNotFoundError
        mock_alert = MagicMock()
        mock_alert.notify.side_effect = sdk_errors.AlertNotFoundError('test-alert-1')
        mock_alert_class.return_value = mock_alert
        
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_file_path = os.path.join(temp_dir, 'test_alerts.csv')
            with open(csv_file_path, 'w') as f:
                f.write('id,environment\ntest-alert-1,production\n')

            # Act
            with patch('click.echo') as mock_echo:
                commands.notify_alerts_from_csv_command(csv_file_path)

            # Assert
            mock_alert.notify.assert_called_once()
            mock_echo.assert_any_call('Alert test-alert-1 not found')
            mock_echo.assert_any_call('1 alerts failed to notify')

    @patch('intezer_analyze_cli.commands.Alert')
    @patch('click.progressbar')
    def test_notify_alerts_from_csv_command_handles_alert_in_progress(self, mock_progressbar, mock_alert_class):
        # Arrange
        create_global_api()

        # Mock progress bar
        mock_progress_context = MagicMock()
        mock_progressbar.return_value.__enter__.return_value = mock_progress_context

        # Mock Alert instance that raises AlertInProgressError
        mock_alert = MagicMock()
        mock_alert.notify.side_effect = sdk_errors.AlertInProgressError('test-alert-1')
        mock_alert_class.return_value = mock_alert

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_file_path = os.path.join(temp_dir, 'test_alerts.csv')
            with open(csv_file_path, 'w') as f:
                f.write('id,environment\ntest-alert-1,production\n')

            # Act
            with patch('click.echo') as mock_echo:
                commands.notify_alerts_from_csv_command(csv_file_path)

            # Assert
            mock_alert.notify.assert_called_once()
            mock_echo.assert_any_call('Alert test-alert-1 is still in progress')
            mock_echo.assert_any_call('1 alerts failed to notify')


class CommandConnectAlertDataSourceSpec(CliSpec):
    def setUp(self):
        super(CommandConnectAlertDataSourceSpec, self).setUp()

        self.mock_api_client = MagicMock()
        api_patcher = patch('intezer_analyze_cli.connector_commands.api.get_global_api',
                            return_value=self.mock_api_client)
        api_patcher.start()
        self.addCleanup(api_patcher.stop)

        raise_for_status_patcher = patch('intezer_analyze_cli.connector_commands.raise_for_status')
        raise_for_status_patcher.start()
        self.addCleanup(raise_for_status_patcher.stop)

    def test_connect_prints_connector_id(self):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'result_url': '/alerts-data-sources/acme-corp/connect-status',
            'connector_id': 'conn-123-abc'
        }
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = mock_response

        config_file = io.StringIO('{}')

        # Act
        with patch('click.echo') as mock_echo:
            connector_commands.connect_alert_data_source_command(
                source='crowdstrike',
                name='acme-corp',
                config_file=config_file,
                resolve_false_positive=False,
                noting=False,
                auto_endpoint_scan=False,
                wait=False
            )

        # Assert
        mock_echo.assert_any_call('Connector ID: conn-123-abc')

    def test_connect_builds_correct_request_body(self):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {'result_url': '/alerts-data-sources/acme-corp/connect-status'}
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = mock_response

        config_data = {'crowdstrike': {'client_secret': 'secret', 'client_id': 'id123'}}
        config_file = io.StringIO(json.dumps(config_data))

        # Act
        connector_commands.connect_alert_data_source_command(
            source='crowdstrike',
            name='acme-corp',
            config_file=config_file,
            resolve_false_positive=True,
            noting=False,
            auto_endpoint_scan=True,
            wait=False
        )

        # Assert
        expected_body = {
            'alert_source': 'crowdstrike',
            'connector_name': 'acme-corp',
            'is_resolve_false_positive_enabled': True,
            'is_noting_enabled': False,
            'is_auto_endpoint_scan_enabled': True,
            'crowdstrike': {'client_secret': 'secret', 'client_id': 'id123'}
        }
        self.mock_api_client.request_with_refresh_expired_access_token.assert_called_once_with(
            method='POST',
            path='/alerts-data-sources/connect',
            data=expected_body
        )

    @patch.dict(os.environ, {'INTEZER_TENANT_ID': 'tenant-123'})
    def test_connect_includes_tenant_id_when_env_var_set(self):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {'result_url': '/alerts-data-sources/acme-corp/connect-status'}
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = mock_response

        config_file = io.StringIO('{}')

        # Act
        connector_commands.connect_alert_data_source_command(
            source='crowdstrike',
            name='acme-corp',
            config_file=config_file,
            resolve_false_positive=False,
            noting=False,
            auto_endpoint_scan=False,
            wait=False
        )

        # Assert
        call_kwargs = self.mock_api_client.request_with_refresh_expired_access_token.call_args
        self.assertEqual(call_kwargs[1]['data']['tenant_id'], 'tenant-123')

    def test_connect_aborts_when_invalid_connector_name(self):
        # Arrange
        config_file = io.StringIO('{}')

        # Act & Assert
        with self.assertRaises(click.exceptions.Abort):
            connector_commands.connect_alert_data_source_command(
                source='crowdstrike',
                name='INVALID_NAME!',
                config_file=config_file,
                resolve_false_positive=False,
                noting=False,
                auto_endpoint_scan=False,
                wait=False
            )

        self.mock_api_client.request_with_refresh_expired_access_token.assert_not_called()

    def test_connect_aborts_when_invalid_json_config(self):
        # Arrange
        config_file = io.StringIO('{invalid json}')

        # Act & Assert
        with patch('click.echo') as mock_echo:
            with self.assertRaises(click.exceptions.Abort):
                connector_commands.connect_alert_data_source_command(
                    source='crowdstrike',
                    name='acme-corp',
                    config_file=config_file,
                    resolve_false_positive=False,
                    noting=False,
                    auto_endpoint_scan=False,
                    wait=False
                )

            echo_calls = [str(c) for c in mock_echo.call_args_list]
            self.assertTrue(any('Invalid JSON' in c for c in echo_calls))

    @patch('intezer_analyze_cli.connector_commands._wait_for_connector_status')
    def test_connect_calls_wait_when_flag_is_set(self, mock_wait):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {'result_url': '/alerts-data-sources/acme-corp/connect-status'}
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = mock_response

        config_file = io.StringIO('{}')

        # Act
        connector_commands.connect_alert_data_source_command(
            source='crowdstrike',
            name='acme-corp',
            config_file=config_file,
            resolve_false_positive=False,
            noting=False,
            auto_endpoint_scan=False,
            wait=True
        )

        # Assert
        mock_wait.assert_called_once_with('/alerts-data-sources/acme-corp/connect-status')

    @patch('intezer_analyze_cli.connector_commands._wait_for_connector_status')
    def test_connect_does_not_call_wait_when_flag_is_false(self, mock_wait):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {'result_url': '/alerts-data-sources/acme-corp/connect-status'}
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = mock_response

        config_file = io.StringIO('{}')

        # Act
        connector_commands.connect_alert_data_source_command(
            source='crowdstrike',
            name='acme-corp',
            config_file=config_file,
            resolve_false_positive=False,
            noting=False,
            auto_endpoint_scan=False,
            wait=False
        )

        # Assert
        mock_wait.assert_not_called()


class CommandDeactivateAlertDataSourceSpec(CliSpec):
    def setUp(self):
        super(CommandDeactivateAlertDataSourceSpec, self).setUp()

        self.mock_api_client = MagicMock()
        api_patcher = patch('intezer_analyze_cli.connector_commands.api.get_global_api',
                            return_value=self.mock_api_client)
        api_patcher.start()
        self.addCleanup(api_patcher.stop)

        raise_for_status_patcher = patch('intezer_analyze_cli.connector_commands.raise_for_status')
        raise_for_status_patcher.start()
        self.addCleanup(raise_for_status_patcher.stop)

    def test_deactivate_calls_correct_api_path(self):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {'result_url': '/alerts-data-sources/acme-corp/connect-status'}
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = mock_response

        # Act
        connector_commands.deactivate_alert_data_source_command(connector_id='acme-corp', wait=False)

        # Assert
        self.mock_api_client.request_with_refresh_expired_access_token.assert_called_once_with(
            method='POST',
            path='/alerts-data-sources/acme-corp/deactivate'
        )

    @patch('intezer_analyze_cli.connector_commands._wait_for_connector_status')
    def test_deactivate_calls_wait_when_flag_is_set(self, mock_wait):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {'result_url': '/alerts-data-sources/acme-corp/connect-status'}
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = mock_response

        # Act
        connector_commands.deactivate_alert_data_source_command(connector_id='acme-corp', wait=True)

        # Assert
        mock_wait.assert_called_once_with('/alerts-data-sources/acme-corp/connect-status')


class CommandActivateAlertDataSourceSpec(CliSpec):
    def setUp(self):
        super(CommandActivateAlertDataSourceSpec, self).setUp()

        self.mock_api_client = MagicMock()
        api_patcher = patch('intezer_analyze_cli.connector_commands.api.get_global_api',
                            return_value=self.mock_api_client)
        api_patcher.start()
        self.addCleanup(api_patcher.stop)

        raise_for_status_patcher = patch('intezer_analyze_cli.connector_commands.raise_for_status')
        raise_for_status_patcher.start()
        self.addCleanup(raise_for_status_patcher.stop)

    def test_activate_calls_correct_api_path(self):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {'result_url': '/alerts-data-sources/acme-corp/connect-status'}
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = mock_response

        # Act
        connector_commands.reactivate_alert_data_source_command(connector_id='acme-corp', wait=False)

        # Assert
        self.mock_api_client.request_with_refresh_expired_access_token.assert_called_once_with(
            method='POST',
            path='/alerts-data-sources/acme-corp/reactivate'
        )

    @patch('intezer_analyze_cli.connector_commands._wait_for_connector_status')
    def test_activate_calls_wait_when_flag_is_set(self, mock_wait):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {'result_url': '/alerts-data-sources/acme-corp/connect-status'}
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = mock_response

        # Act
        connector_commands.reactivate_alert_data_source_command(connector_id='acme-corp', wait=True)

        # Assert
        mock_wait.assert_called_once_with('/alerts-data-sources/acme-corp/connect-status')


class CommandUpdateAlertDataSourceSpec(CliSpec):
    def setUp(self):
        super(CommandUpdateAlertDataSourceSpec, self).setUp()

        self.mock_api_client = MagicMock()
        api_patcher = patch('intezer_analyze_cli.connector_commands.api.get_global_api',
                            return_value=self.mock_api_client)
        api_patcher.start()
        self.addCleanup(api_patcher.stop)

        raise_for_status_patcher = patch('intezer_analyze_cli.connector_commands.raise_for_status')
        raise_for_status_patcher.start()
        self.addCleanup(raise_for_status_patcher.stop)

    def test_update_calls_correct_api_path_with_put(self):
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {'result_url': '/alerts-data-sources/acme-corp/connect-status'}
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = mock_response

        config_data = {'crowdstrike': {'client_secret': 'new-secret'}}
        config_file = io.StringIO(json.dumps(config_data))

        # Act
        connector_commands.update_alert_data_source_command(
            connector_id='acme-corp',
            config_file=config_file,
            wait=False
        )

        # Assert
        self.mock_api_client.request_with_refresh_expired_access_token.assert_called_once_with(
            method='PUT',
            path='/alerts-data-sources/acme-corp',
            data=config_data
        )

    def test_update_returns_immediately_on_200_ok(self):
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = mock_response

        config_file = io.StringIO('{}')

        # Act
        with patch('click.echo') as mock_echo:
            connector_commands.update_alert_data_source_command(
                connector_id='acme-corp',
                config_file=config_file,
                wait=True
            )

        # Assert
        mock_echo.assert_called_once_with('Update applied for "acme-corp"')
        mock_response.json.assert_not_called()

    def test_update_aborts_when_invalid_json_config(self):
        # Arrange
        config_file = io.StringIO('not valid json')

        # Act & Assert
        with patch('click.echo') as mock_echo:
            with self.assertRaises(click.exceptions.Abort):
                connector_commands.update_alert_data_source_command(
                    connector_id='acme-corp',
                    config_file=config_file,
                    wait=False
                )

            echo_calls = [str(c) for c in mock_echo.call_args_list]
            self.assertTrue(any('Invalid JSON' in c for c in echo_calls))

    @patch('intezer_analyze_cli.connector_commands._wait_for_connector_status')
    def test_update_calls_wait_when_flag_is_set(self, mock_wait):
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {'result_url': '/alerts-data-sources/acme-corp/connect-status'}
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = mock_response

        config_file = io.StringIO('{}')

        # Act
        connector_commands.update_alert_data_source_command(
            connector_id='acme-corp',
            config_file=config_file,
            wait=True
        )

        # Assert
        mock_wait.assert_called_once_with('/alerts-data-sources/acme-corp/connect-status')


class CommandWaitForConnectorStatusSpec(CliSpec):
    def setUp(self):
        super(CommandWaitForConnectorStatusSpec, self).setUp()

        self.mock_api_client = MagicMock()
        api_patcher = patch('intezer_analyze_cli.connector_commands.api.get_global_api',
                            return_value=self.mock_api_client)
        api_patcher.start()
        self.addCleanup(api_patcher.stop)

        raise_for_status_patcher = patch('intezer_analyze_cli.connector_commands.raise_for_status')
        self.mock_raise_for_status = raise_for_status_patcher.start()
        self.addCleanup(raise_for_status_patcher.stop)

        sleep_patcher = patch('intezer_analyze_cli.connector_commands.time.sleep')
        self.mock_sleep = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

        self.mock_spinner = MagicMock()
        yaspin_patcher = patch('intezer_analyze_cli.connector_commands.yaspin')
        self.mock_yaspin = yaspin_patcher.start()
        self.mock_yaspin.return_value.__enter__ = MagicMock(return_value=self.mock_spinner)
        self.mock_yaspin.return_value.__exit__ = MagicMock(return_value=False)
        self.addCleanup(yaspin_patcher.stop)

    def _make_status_response(self, status, error=None):
        mock_response = MagicMock()
        result = {'status': status}
        if error:
            result['error'] = error
        mock_response.json.return_value = result
        return mock_response

    def test_wait_returns_on_active_status(self):
        # Arrange
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = \
            self._make_status_response('active')

        # Act
        connector_commands._wait_for_connector_status('/alerts-data-sources/acme-corp/connect-status')

        # Assert
        self.mock_api_client.request_with_refresh_expired_access_token.assert_called_once_with(
            method='GET',
            path='/alerts-data-sources/acme-corp/connect-status',
            base_url=self.mock_api_client.base_url.removesuffix().rstrip()
        )
        self.mock_sleep.assert_not_called()

    def test_wait_returns_on_pending_status(self):
        # Arrange
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = \
            self._make_status_response('pending')

        # Act
        connector_commands._wait_for_connector_status('/alerts-data-sources/acme-corp/connect-status')

        # Assert
        self.mock_sleep.assert_not_called()

    def test_wait_returns_on_deactivated_status(self):
        # Arrange
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = \
            self._make_status_response('deactivated')

        # Act
        connector_commands._wait_for_connector_status('/alerts-data-sources/acme-corp/connect-status')

        # Assert
        self.mock_sleep.assert_not_called()

    def test_wait_raises_on_credentials_verification_failed(self):
        # Arrange
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = \
            self._make_status_response('credentials_verification_failed', error='Bad credentials')

        # Act & Assert
        with self.assertRaises(click.exceptions.ClickException) as ctx:
            connector_commands._wait_for_connector_status('/alerts-data-sources/acme-corp/connect-status')

        self.assertIn('credentials_verification_failed', str(ctx.exception))

    def test_wait_raises_on_deployment_failed(self):
        # Arrange
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = \
            self._make_status_response('deployment_failed')

        # Act & Assert
        with self.assertRaises(click.exceptions.ClickException) as ctx:
            connector_commands._wait_for_connector_status('/alerts-data-sources/acme-corp/connect-status')

        self.assertIn('deployment_failed', str(ctx.exception))

    def test_wait_raises_on_update_failed(self):
        # Arrange
        self.mock_api_client.request_with_refresh_expired_access_token.return_value = \
            self._make_status_response('update_failed')

        # Act & Assert
        with self.assertRaises(click.exceptions.ClickException):
            connector_commands._wait_for_connector_status('/alerts-data-sources/acme-corp/connect-status')

    def test_wait_polls_through_in_progress_statuses(self):
        # Arrange
        self.mock_api_client.request_with_refresh_expired_access_token.side_effect = [
            self._make_status_response('verifying_credentials'),
            self._make_status_response('deployment_in_progress'),
            self._make_status_response('active'),
        ]

        # Act
        connector_commands._wait_for_connector_status('/alerts-data-sources/acme-corp/connect-status')

        # Assert
        self.assertEqual(self.mock_api_client.request_with_refresh_expired_access_token.call_count, 3)
        self.assertEqual(self.mock_sleep.call_count, 2)
        self.mock_sleep.assert_called_with(5)

    def test_wait_prints_status_transitions(self):
        # Arrange
        self.mock_api_client.request_with_refresh_expired_access_token.side_effect = [
            self._make_status_response('verifying_credentials'),
            self._make_status_response('verifying_credentials'),
            self._make_status_response('active'),
        ]

        # Act
        connector_commands._wait_for_connector_status('/alerts-data-sources/acme-corp/connect-status')

        # Assert - should print verifying_credentials only once (deduped), then active via sp.write
        self.mock_spinner.write.assert_any_call('Status: verifying_credentials')
        self.mock_spinner.write.assert_any_call('Status: active')
        # verifying_credentials should appear exactly once in write calls
        status_calls = [c for c in self.mock_spinner.write.call_args_list
                        if 'Status: verifying_credentials' in str(c)]
        self.assertEqual(len(status_calls), 1)

