import os
import tempfile
import unittest.mock
import uuid
from pathlib import Path
from tempfile import tempdir
from unittest.mock import MagicMock
from unittest.mock import patch

import click.exceptions
import intezer_sdk.endpoint_analysis
import intezer_sdk.base_analysis
from intezer_sdk import errors as sdk_errors
import intezer_analyze_cli.key_store as key_store
from intezer_analyze_cli import commands
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

