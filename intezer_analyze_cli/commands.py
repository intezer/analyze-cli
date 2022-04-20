import logging
import os
from typing import Optional

import click
from intezer_sdk import api
from intezer_sdk import consts as sdk_consts
from intezer_sdk import errors as sdk_errors
from intezer_sdk.analysis import Analysis
from intezer_sdk.index import Index

from intezer_analyze_cli import key_store
from intezer_analyze_cli import utilities
from intezer_analyze_cli.config import default_config
from intezer_analyze_cli.utilities import is_hidden

logger = logging.getLogger('intezer_client')


def login(api_key: str, api_url: str):
    try:
        if api_url:
            key_store.store_default_url(api_url)
        else:
            api_url = default_config.api_url
            key_store.delete_default_url()

        api.set_global_api(api_key, default_config.api_version, api_url)
        api.get_global_api().set_session()
        key_store.store_api_key(api_key)
        click.echo('You have successfully logged in')
    except sdk_errors.InvalidApiKey:
        click.echo('Invalid API key error, please contact us at support@intezer.com '
                   'and attach the log file in {}'.format(utilities.log_file_path))
        raise click.Abort()


def analyze_file_command(file_path: str,
                         disable_dynamic_unpacking: bool,
                         disable_static_unpacking: bool,
                         code_item_type: str):
    if disable_dynamic_unpacking and not utilities.is_supported_file(file_path):
        click.echo('File is not PE, ELF, DEX or APK')
        return

    try:
        analysis = Analysis(file_path=file_path,
                            code_item_type=code_item_type,
                            disable_dynamic_unpacking=disable_dynamic_unpacking,
                            disable_static_unpacking=disable_static_unpacking)
        analysis.send()
        if default_config.is_cloud:
            click.echo(
                'Analysis created. In order to check its result, go to: {}/{}'.format(default_config.analyses_url,
                                                                                      analysis.analysis_id))
        else:
            click.echo('Analysis created. In order to check its result go to Intezer Analyze history page')
    except sdk_errors.IntezerError as e:
        click.echo('Analyze error: {}'.format(e))


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
                        Analysis(file_path=file_path,
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
        if default_config.is_cloud:
            click.echo('{} analysis created. In order to check their results, go to: {}'.format(
                success_number,
                default_config.analyses_url)
            )
        else:
            click.echo('{} analysis created. In order to check their results '
                       'go to Intezer Analyze history page'.format(success_number))

    if failed_number != 0:
        click.echo('{} analysis failed'.format(failed_number))

    if unsupported_number != 0:
        click.echo('{} unsupported files'.format(unsupported_number))


def analyze_by_txt_file_command(path: str):
    try:
        hashes = get_hashes_from_file(path)
        with click.progressbar(length=len(hashes),
                               label='Analyze files',
                               show_pos=True,
                               width=0) as progressbar:
            for file_hash in hashes:
                try:
                    Analysis(file_hash=file_hash).send()
                except sdk_errors.HashDoesNotExistError:
                    click.echo('Hash: {} does not exist in the system'.format(file_hash))
                except sdk_errors.IntezerError:
                    click.echo('Error occurred with hash: {}'.format(file_hash))
                progressbar.update(1)

            if default_config.is_cloud:
                click.echo('analysis created. In order to check their results, go to: {}'
                           .format(default_config.analyses_url))
            else:
                click.echo(
                    'analysis created. In order to check their results go to Intezer Analyze history page')
    except IOError:
        click.echo('No read permissions for {}'.format(path))
        click.Abort()


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
                    index_exceptions.append('Failed to index hash: {} error: {}'.format(sha256, e))
                except sdk_errors.IndexFailed:
                    index_exceptions.append('Failed to index hash: {} error: {}'.format(sha256, e))
                index_progress.update(1)

        echo_exceptions(index_exceptions)

        if default_config.is_cloud:
            click.echo('Index updated. In order to check their results, go to: {}'
                       .format(default_config.index_results_url))
        else:
            click.echo(
                'Index updated. In order to check the results go to Private Indexed Files under Analysis Reports')
    except IOError:
        click.echo('No read permissions for {}'.format(path))
        click.Abort()


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
        return None, 'Index error: {} Error occurred with hash: {}'.format(e, sha256)


def index_file_command(file_path: str, index_as: str, family_name: Optional[str]):
    if not utilities.is_supported_file(file_path):
        click.echo('File is not PE, ELF, DEX or APK')
        return
    try:
        index = Index(index_as=sdk_consts.IndexType.from_str(index_as), file_path=file_path, family_name=family_name)
        index.send(wait=True)
        click.echo('Finish index: {} with status: {}'.format(index.index_id, index.status))
    except sdk_errors.IntezerError as e:
        click.echo('Index error: {}'.format(e))


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
                    click.echo('Could not open {} because it is not a supported file type'.format(file_name))
                    progressbar.update(1)
                    continue

                try:
                    index = Index(index_as=sdk_consts.IndexType.from_str(index_as),
                                  file_path=file_path,
                                  family_name=family_name)
                    index.send()
                    indexes_results.append({'file_name': file_name, 'index': index})
                except sdk_errors.IntezerError:
                    click.echo('error occurred during indexing of {}'.format(file_name))
                    progressbar.update(1)

            for index_result in indexes_results:
                try:
                    index_result['index'].wait_for_completion()
                    click.echo('Index: {} , File: {} , finished with status: {}'.format(index_result['index'].index_id,
                                                                                        index_result['file_name'],
                                                                                        index_result['index'].status))
                    progressbar.update(1)
                except Exception:
                    click.echo('error occurred during indexing of {}'.format(index_result['file_name']))
                    progressbar.update(1)
