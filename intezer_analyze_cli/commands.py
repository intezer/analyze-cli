import logging
import os
from io import BytesIO
from typing import Optional
from email.utils import parsedate_to_datetime

import click
from intezer_sdk import api
from intezer_sdk import consts as sdk_consts
from intezer_sdk import errors as sdk_errors
from intezer_sdk.alerts import Alert
from intezer_sdk.analysis import FileAnalysis
from intezer_sdk.endpoint_analysis import EndpointAnalysis
from intezer_sdk.index import Index

from intezer_analyze_cli import key_store
from intezer_analyze_cli import utilities
from intezer_analyze_cli.config import default_config
from intezer_analyze_cli.utilities import is_hidden

logger = logging.getLogger('intezer_cli')


def login(api_key: str, api_url: str):
    try:
        if api_url:
            key_store.store_default_url(api_url)
        else:
            api_url = default_config.api_url
            key_store.delete_default_url()

        api.set_global_api(api_key, default_config.api_version, api_url)
        api.get_global_api().authenticate()
        key_store.store_api_key(api_key)
        click.echo('You have successfully logged in')
    except sdk_errors.InvalidApiKey:
        click.echo(f'Invalid API key error, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}')
        raise click.Abort()


def analyze_file_command(file_path: str,
                         disable_dynamic_unpacking: bool,
                         disable_static_unpacking: bool,
                         code_item_type: str):
    if disable_dynamic_unpacking and not utilities.is_supported_file(file_path):
        click.echo('File is not PE, ELF, DEX or APK')
        return

    try:
        analysis = FileAnalysis(file_path=file_path,
                                code_item_type=code_item_type,
                                disable_dynamic_unpacking=disable_dynamic_unpacking,
                                disable_static_unpacking=disable_static_unpacking)
        analysis.send()
        analysis_page_url = default_config.file_analysis_url_template.format(
            system_url=default_config.api_url.replace('/api/', ''),
            analysis_id=analysis.analysis_id
        )
        click.echo(f'Analysis created. In order to check its result, go to: {analysis_page_url}')
    except sdk_errors.IntezerError as e:
        click.echo(f'Analyze error: {e}')


def analyze_directory_command(path: str,
                              disable_dynamic_unpacking: bool,
                              disable_static_unpacking: bool,
                              code_item_type: str,
                              ignore_directory_count_limit: bool):
    success_number = 0
    failed_number = 0
    unsupported_number = 0

    for root, dirs, files in os.walk(path):
        files = [f for f in files if not is_hidden(os.path.join(root, f))]
        dirs[:] = [d for d in dirs if not is_hidden(os.path.join(root, d))]

        number_of_files = len(files)
        if not ignore_directory_count_limit:
            utilities.check_should_continue_for_large_dir(number_of_files, default_config.unusual_amount_in_dir)
        if not files:
            continue

        with click.progressbar(length=number_of_files,
                               label='Sending files for analysis',
                               show_pos=True) as progressbar:
            for file_name in files:
                file_path = os.path.join(root, file_name)
                if disable_dynamic_unpacking and not utilities.is_supported_file(file_path):
                    unsupported_number += 1
                else:
                    try:
                        FileAnalysis(file_path=file_path,
                                     code_item_type=code_item_type,
                                     disable_dynamic_unpacking=disable_dynamic_unpacking,
                                     disable_static_unpacking=disable_static_unpacking).send()
                        success_number += 1
                    except sdk_errors.IntezerError as ex:
                        # We cannot continue analyzing the directory if the account is out of quota
                        if isinstance(ex, sdk_errors.InsufficientQuota):
                            logger.error('Failed to analyze %s', file_path)
                            raise

                        logger.exception('Error while analyzing directory')
                        failed_number += 1
                    except Exception:
                        logger.exception('Failed to analyze %s', file_path)
                        failed_number += 1

                progressbar.update(1)

    if success_number != 0:
        analyses_page_url = default_config.history_page_url_template.format(
            system_url=default_config.api_url.replace('/api/', ''),
            tab_name=default_config.file_analyses_tab_name
        )
        click.echo(f'{success_number} analysis created. In order to check their results, go to: {analyses_page_url}')

    if failed_number != 0:
        click.echo(f'{failed_number} analysis failed')

    if unsupported_number != 0:
        click.echo(f'{unsupported_number} unsupported files')


def analyze_by_txt_file_command(path: str):
    try:
        hashes = get_hashes_from_file(path)
        with click.progressbar(length=len(hashes),
                               label='Analyze files',
                               show_pos=True,
                               width=0) as progressbar:
            for file_hash in hashes:
                try:
                    FileAnalysis(file_hash=file_hash).send()
                except sdk_errors.HashDoesNotExistError:
                    click.echo(f'Hash: {file_hash} does not exist in the system')
                    logger.info('Hash not exists', extra=dict(file_hash=file_hash))
                except sdk_errors.IntezerError:
                    click.echo(f'Error occurred with hash: {file_hash}')
                    logger.exception('Error occurred with hash', extra=dict(file_hash=file_hash))
                progressbar.update(1)
            analyses_page_url = default_config.history_page_url_template.format(
                system_url=default_config.api_url.replace('/api/', ''),
                tab_name=default_config.file_analyses_tab_name
            )
            click.echo(f'analysis created. In order to check their results, go to: {analyses_page_url}')
    except IOError:
        click.echo(f'No read permissions for {path}')
        logger.exception('Error reading hashes file', extra=dict(path=path))
        raise click.Abort()


def index_by_txt_file_command(path: str, index_as: str, family_name: str):
    try:
        hashes = get_hashes_from_file(path)
        index_exceptions = []
        index_operations = []
        with click.progressbar(length=len(hashes),
                               label='Indexing files',
                               show_pos=True,
                               width=0) as upload_progress:
            for sha256 in hashes:
                index_operation, index_exception = index_hash_command(sha256, index_as, family_name)
                if index_operation:
                    index_operations.append((index_operation, sha256))
                else:
                    index_exceptions.append(index_exception)
                upload_progress.update(1)
        click.echo('Indexing sent')

        echo_exceptions(index_exceptions)
        index_exceptions = []
        with click.progressbar(length=len(index_operations),
                               label='Waiting for indexing to finish',
                               show_pos=True,
                               width=0) as index_progress:
            for index_operation, sha256 in index_operations:
                try:
                    index_operation.wait_for_completion()
                except sdk_errors.IntezerError as e:
                    index_exceptions.append(f'Failed to index hash: {sha256} error: {e}')
                    logger.exception('Failed to index hash', extra=dict(sha256=sha256))
                except sdk_errors.IndexFailed:
                    index_exceptions.append(f'Failed to index hash: {sha256} error: {e}')
                    logger.exception('Failed to index hash', extra=dict(sha256=sha256))
                index_progress.update(1)

        echo_exceptions(index_exceptions)

        private_index_page_url = default_config.history_page_url_template.format(
            system_url=default_config.api_url.replace('/api/', ''),
            tab_name=default_config.index_results_tab_name
        )
        click.echo(f'Index updated. In order to check their results, go to: {private_index_page_url}')

    except IOError:
        click.echo(f'No read permissions for {path}')
        logger.exception('Error reading hashes file', extra=dict(path=path))
        raise click.Abort()


def echo_exceptions(exceptions):
    if exceptions:
        click.echo('Some hashes failed')
        for exception in exceptions:
            click.echo(exception)


def get_hashes_from_file(path):
    with open(path, 'r') as file:
        hashes = [line.strip('\n') for line in file.readlines()]
        return hashes


def index_hash_command(sha256: str, index_as: str, family_name: Optional[str]):
    try:
        index_operation = Index(index_as=sdk_consts.IndexType.from_str(index_as),
                                sha256=sha256,
                                family_name=family_name)
        index_operation.send(wait=False)
        return index_operation, None
    except sdk_errors.IntezerError as e:
        logger.exception('Failed to index hash', extra=dict(sha256=sha256))
        return None, f'Index error: {e} Error occurred with hash: {sha256}'


def index_file_command(file_path: str, index_as: str, family_name: Optional[str]):
    if not utilities.is_supported_file(file_path):
        click.echo('File is not PE, ELF, DEX or APK')
        return
    try:
        index = Index(index_as=sdk_consts.IndexType.from_str(index_as), file_path=file_path, family_name=family_name)
        index.send(wait=True)
        click.echo(f'Finish index: {index.index_id} with status: {index.status}')
    except sdk_errors.IntezerError as e:
        logger.exception('Failed to index file', extra=dict(file_path=file_path))
        click.echo(f'Index error: {e}')


def index_directory_command(directory_path: str,
                            index_as: str,
                            family_name: Optional[str],
                            ignore_directory_count_limit: bool):
    indexes_results = []

    for root, dirs, files in os.walk(directory_path):
        files = [f for f in files if not is_hidden(os.path.join(root, f))]
        dirs[:] = [d for d in dirs if not is_hidden(os.path.join(root, d))]

        number_of_files = len(files)
        if not ignore_directory_count_limit:
            utilities.check_should_continue_for_large_dir(number_of_files, default_config.unusual_amount_in_dir)
        with click.progressbar(length=number_of_files,
                               label='Index files',
                               show_pos=True,
                               width=0) as progressbar:
            for file_name in files:
                file_path = os.path.join(root, file_name)

                if not utilities.is_supported_file(file_path):
                    click.echo(f'Could not open {file_name} because it is not a supported file type')
                    progressbar.update(1)
                    continue

                try:
                    index = Index(index_as=sdk_consts.IndexType.from_str(index_as),
                                  file_path=file_path,
                                  family_name=family_name)
                    index.send()
                    indexes_results.append({'file_name': file_name, 'index': index})
                except sdk_errors.IntezerError:
                    logger.exception('Failed to index file', extra=dict(file_name=file_name))
                    click.echo(f'Error occurred during indexing of {file_name}')
                    progressbar.update(1)

            for index_result in indexes_results:
                try:
                    index_result['index'].wait_for_completion()
                    click.echo(f'Index: {index_result["index"].index_id} ,'
                               f' File: {index_result["file_name"]} ,'
                               f' finished with status: {index_result["index"].status}')
                    progressbar.update(1)
                except Exception:
                    logger.exception('Failed to index file', extra=dict(file_name=index_result['file_name']))
                    click.echo(f'Error occurred during indexing of {index_result["file_name"]}')
                    progressbar.update(1)


def upload_offline_endpoint_scan(offline_scan_directory: str, force: bool = False):
    try:
        if not force and _was_directory_already_sent(offline_scan_directory):
            raise click.Abort()
        endpoint_analysis = EndpointAnalysis(offline_scan_directory=offline_scan_directory)
        endpoint_analysis.send(wait=False)
        if not endpoint_analysis.analysis_id:
            raise RuntimeError('Error encountered while sending offline scan, server did not return analysis id')
        _create_analysis_id_file(offline_scan_directory, endpoint_analysis.analysis_id)

        endpoint_analysis_page_url = default_config.endpoint_analysis_url_template.format(
            system_url=default_config.api_url.replace('/api/', ''),
            endpoint_analysis_id=endpoint_analysis.analysis_id
        )

        click.echo(f'Analysis created. In order to check its result, go to: {endpoint_analysis_page_url}')

    except sdk_errors.IntezerError as e:
        click.echo(f'Analyze error: {e}')
        logger.exception('Failed to analyze offline scan')
        raise
    return endpoint_analysis.analysis_id


def upload_multiple_offline_endpoint_scans(offline_scans_root_directory: str,
                                           force: bool = False):
    success_number = 0
    failed_number = 0

    directories = _get_scan_subdirectories(offline_scans_root_directory)

    with click.progressbar(length=len(directories),
                           label='Sending offline endpoint scans for analysis',
                           show_pos=True) as progressbar:
        for scan_dir in directories:
            offline_scan_directory = os.path.join(offline_scans_root_directory, scan_dir)
            try:
                upload_offline_endpoint_scan(offline_scan_directory, force)
                success_number += 1
            except Exception as e:
                logger.exception(f'Error while analyzing directory {scan_dir}: {str(e)}')
                failed_number += 1
            finally:
                progressbar.update(1)

    if success_number != 0:
        endpoint_analyses_page_url = default_config.history_page_url_template.format(
            system_url=default_config.api_url.replace('/api/', ''),
            tab_name=default_config.endpoint_analyses_tab_name
        )
        click.echo(
            f'{success_number} analysis created. In order to check their results, go to: {endpoint_analyses_page_url}')
    if failed_number != 0:
        click.echo(f'{failed_number} offline endpoint scans failed to send')


def send_phishing_emails_from_directory_command(path: str,
                                                ignore_directory_count_limit: bool = False):
    success_number = 0
    failed_number = 0
    unsupported_number = 0
    emails_dates = []

    for root, dirs, files in os.walk(path):
        files = [f for f in files if not is_hidden(os.path.join(root, f))]

        number_of_files = len(files)
        if not ignore_directory_count_limit:
            utilities.check_should_continue_for_large_dir(number_of_files, default_config.unusual_amount_in_dir)
        if not files:
            continue

        with click.progressbar(length=number_of_files,
                               label='Sending files for analysis',
                               show_pos=True) as progressbar:
            for file_name in files:
                email_path = os.path.join(root, file_name)
                with open(email_path, 'rb') as email_file:
                    binary_data = BytesIO(email_file.read())
                is_eml, date = utilities.is_eml_file(binary_data)
                if not is_eml:
                    unsupported_number += 1
                    continue
                try:
                    Alert.send_phishing_email(raw_email=binary_data)
                    success_number += 1
                    if date:
                        try:
                            timestamp = parsedate_to_datetime(date).timestamp()
                            emails_dates.append(timestamp)
                        except Exception:
                            continue

                except sdk_errors.IntezerError as ex:
                    logger.exception('Error while analyzing directory')
                    failed_number += 1
                except Exception:
                    logger.exception(f'Failed to analyze {email_path}')
                    failed_number += 1

                progressbar.update(1)

    if success_number != 0:
        alerts_page_url = default_config.phishing_alerts_by_time_template.format(
            system_url=default_config.api_url.replace('/api/', '')
        )
        earliest_email_timestamp = int(min(emails_dates)) if emails_dates else None
        latest_email_timestamp = int(max(emails_dates)) if emails_dates else None
        if earliest_email_timestamp and latest_email_timestamp:
            alerts_page_url = f'{alerts_page_url}&start_time={earliest_email_timestamp}&end_time={latest_email_timestamp}'
        click.echo(f'{success_number} alerts created. In order to check their results, go to: {alerts_page_url}')

    if failed_number != 0:
        click.echo(f'{failed_number} scans failed')

    if unsupported_number != 0:
        click.echo(f'{unsupported_number} unsupported files')


def _get_scan_subdirectories(offline_scans_root_directory):
    directories = [d for d in os.listdir(offline_scans_root_directory) if
                   os.path.isdir(os.path.join(offline_scans_root_directory, d)) and
                   not is_hidden(os.path.join(offline_scans_root_directory, d))]
    for mandatory_directory in ('files', 'fileless', 'memory_modules'):
        if mandatory_directory not in directories:
            click.echo(f'Directory "{mandatory_directory}" is missing')
            raise click.Abort()
        directories.remove(mandatory_directory)
    return directories


def _was_directory_already_sent(path: str) -> bool:
    try:
        if os.path.isfile(os.path.join(path, 'analysis_id.txt')):
            with open(os.path.join(path, 'analysis_id.txt')) as f:
                analysis_id = f.read()

            endpoint_analysis_page_url = default_config.endpoint_analysis_url_template.format(
                system_url=default_config.api_url.replace('/api/', ''),
                endpoint_analysis_id=analysis_id
            )

            click.echo(f'Scan: {os.path.dirname(path)} has already been sent for analysis. '
                       f'See: {endpoint_analysis_page_url}')
            return True
    except Exception:
        logger.exception('Error while reading analysis_id.txt file in directory', extra=dict(path=path))
        click.echo(f'Error while reading analysis_id.txt file in directory {os.path.dirname(path)}')
        raise
    return False


def _create_analysis_id_file(directory: str, analysis_id: str):
    try:
        with open(os.path.join(directory, 'analysis_id.txt'), 'w') as f:
            f.write(analysis_id)
    except Exception:
        logger.exception('Could not create analysis_id.txt file', extra=dict(directory=directory))
        click.echo(f'Could not create analysis_id.txt file in {directory}')
        raise
