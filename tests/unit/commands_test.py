import os
from pathlib import Path

import intezer_analyze_cli.key_store as key_store

from unittest.mock import MagicMock
from unittest.mock import patch

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

        send_analyze_patcher = patch('intezer_sdk.analysis.Analysis.send')
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
