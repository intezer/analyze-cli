import logging
import os

import click
from intezer_sdk import api
from intezer_sdk import consts as sdk_consts
from intezer_sdk import errors as sdk_errors
from intezer_sdk.analysis import Analysis
from intezer_sdk.index import Index

from intezer_analyze_cli import key_store
from intezer_analyze_cli import utilities
from intezer_analyze_cli.config import default_config

logger = logging.getLogger('intezer_client')


def login(api_key, api_url):
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


def analyze_file_command(file_path, no_unpacking, no_static_unpacking):
    if not utilities.is_supported_file(file_path):
        click.echo('File is not PE, ELF, DEX or APK')
        return

    try:
        analysis = Analysis(file_path=file_path,
                            dynamic_unpacking=no_unpacking,
                            static_unpacking=no_static_unpacking)
        analysis.send()
        if default_config.is_cloud:
            click.echo(
                'Analysis created. In order to check its result, go to: {}/{}'.format(default_config.analyses_url,
                                                                                      analysis.analysis_id))
        else:
            click.echo('Analysis created. In order to check its result go to Intezer Analyze history page')
    except sdk_errors.IntezerError as e:
        click.echo('Analyze error: {}'.format(e))


def analyze_directory_command(path, no_unpacking, no_static_unpacking):
    success_number = 0
    failed_number = 0
    unsupported_number = 0

    for root, dirs, files in os.walk(path):
        number_of_files = len(files)
        utilities.check_should_continue_for_large_dir(number_of_files, default_config.unusual_amount_in_dir)
        with click.progressbar(length=number_of_files,
                               label='Sending files for analysis',
                               show_pos=True) as progressbar:
            for file_name in files:
                file_path = os.path.join(root, file_name)
                if not utilities.is_supported_file(file_path):
                    unsupported_number += 1
                else:
                    try:
                        Analysis(file_path=file_path,
                                 dynamic_unpacking=no_unpacking,
                                 static_unpacking=no_static_unpacking).send()
                        success_number += 1
                    except sdk_errors.IntezerError as ex:
                        # We cannot continue analyzing the directory if the account is out of quota
                        if isinstance(ex, sdk_errors.InsufficientQuota):
                            raise

                        logger.exception('Error while analyzing directory')
                        failed_number += 1

                progressbar.update(1)

    if success_number != 0:
        if default_config.is_cloud:
            click.echo('{} analysis created. In order to check their results, go to: {}'.format(success_number,
                                                                                                default_config.analyses_url))
        else:
            click.echo('{} analysis created. In order to check their results '
                       'go to Intezer Analyze history page'.format(success_number))

    if failed_number != 0:
        click.echo('{} analysis failed'.format(failed_number))

    if unsupported_number != 0:
        click.echo('{} unsupported files'.format(unsupported_number))


def analyze_by_txt_file_command(path):
    try:
        hashes = [line.rstrip('\n') for line in open(path)]
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


def index_file_command(file_path, index_as, family_name=None):
    if not utilities.is_supported_file(file_path):
        click.echo('File is not PE, ELF, DEX or APK')
        return
    try:
        index = Index(index_as=sdk_consts.IndexType.from_str(index_as), file_path=file_path, family_name=family_name)
        index.send(wait=True)
        click.echo('Finish index: {} with status: {}'.format(index.index_id, index.status))
    except sdk_errors.IntezerError as e:
        click.echo('Index error: {}'.format(e))


def index_directory_command(directory_path, index_as, family_name=None):
    indexes_results = []

    for root, dirs, files in os.walk(directory_path):
        number_of_files = len(files)
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
