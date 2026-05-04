import logging
import os

import click
from intezer_sdk import api
from intezer_sdk import consts as sdk_consts
from intezer_sdk import errors as sdk_errors
from intezer_sdk.consts import CodeItemType

from intezer_analyze_cli import __version__
from intezer_analyze_cli import commands
from intezer_analyze_cli import connector_commands
from intezer_analyze_cli import subtenant_commands
from intezer_analyze_cli import key_store
from intezer_analyze_cli import utilities
from intezer_analyze_cli.config import default_config

utilities.init_log('intezer_cli', os.environ.get('INTEZER_DEBUG') == '1')
logger = logging.getLogger('intezer_cli')


class AliasedGroup(click.Group):
    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx)
                   if x.replace('-', '_') == cmd_name.replace('-', '_')]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail(f"Too many matches: {', '.join(sorted(matches))}")

    def resolve_command(self, ctx, args):
        # always return the full command name
        _, cmd, args = super().resolve_command(ctx, args)
        return cmd.name, cmd, args


def create_global_api():
    try:
        api_key = key_store.get_stored_api_key()
        api_url = key_store.get_stored_default_url()

        if not api_key:
            logger.exception('Cant find API key')
            click.echo('Cant find API key, please login')
            raise click.Abort()

        if api_url:
            default_config.api_url = api_url
            default_config.is_cloud = False

        api.set_global_api(api_key, default_config.api_version, default_config.api_url)
        sdk_consts.USER_AGENT += f'/CLI-{__version__}'

    except sdk_errors.InvalidApiKey:
        logger.exception('Invalid api key error')
        click.echo('Invalid API key error, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}')
        raise click.Abort()


@click.group(cls=AliasedGroup, context_settings=dict(help_option_names=['-h', '--help'], max_content_width=120),
             help=f'Intezer Labs Ltd. Intezer CLI {__version__}')
def main_cli():
    pass


@main_cli.command('login', short_help='Login to Intezer Platform')
@click.argument('api_key', type=click.UUID)
@click.argument('api_url', required=False, default=None, type=click.STRING)
def login(api_key: str, api_url: str):
    """Login to Intezer Platform to perform analyses.

    \b
    API_KEY: API key or invite code for Intezer Platform.

    \b
    API_URL: Intezer Platform URL in case you have on premise deployment.

    \b
    Example:
      $ intezer-cli login edb45d954da54e8e980078001d8921cc
    """
    try:
        if api_url:
            if api_url[-1] != '/':
                api_url += '/'
            if not api_url.endswith('/api/'):
                api_url += 'api/'
        commands.login(str(api_key), api_url)
    except click.Abort:
        raise
    except Exception:
        logger.exception('Unexpected error occurred')
        click.echo('Unexpected error occurred, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}')


@main_cli.command('analyze', short_help='Send a file or a directory for analysis')
@click.option('--no-unpacking', is_flag=True, help='Should the analysis skip unpacking')
@click.option('--no-static-extraction', is_flag=True, help='Should the analysis skip static extraction')
@click.option('--code-item-type', type=click.Choice([c.value for c in CodeItemType]), default=None,
              help='The type of the binary file uploaded')
@click.option('--ignore-directory-count-limit',
              is_flag=True,
              help='ignore directory count limit ({} files)'.format(default_config.unusual_amount_in_dir))
@click.argument('path', type=click.Path(exists=True))
def analyze(path: str,
            no_unpacking: bool,
            no_static_extraction: bool,
            code_item_type: str,
            ignore_directory_count_limit: bool):
    """ Send a file or a directory for analysis in Intezer Platform.

    \b
    PATH: Path to file or directory to send the files inside for analysis.

    \b
    Examples:
      Send a single file for analysis:
      $ intezer-cli analyze ~/files/threat.exe.sample
      \b
      Send all files in directory for analysis:
      $ intezer-cli analyze ~/files/files-to-analyze
    """
    try:
        create_global_api()

        if not no_unpacking:
            no_unpacking = None
        if not no_static_extraction:
            no_static_extraction = None

        if os.path.isfile(path):
            commands.analyze_file_command(file_path=path,
                                          disable_dynamic_unpacking=no_unpacking,
                                          disable_static_unpacking=no_static_extraction,
                                          code_item_type=code_item_type)
        else:
            commands.analyze_directory_command(path=path,
                                               disable_dynamic_unpacking=no_unpacking,
                                               disable_static_unpacking=no_static_extraction,
                                               code_item_type=code_item_type,
                                               ignore_directory_count_limit=ignore_directory_count_limit)
    except click.Abort:
        raise
    except sdk_errors.InsufficientQuota:
        logger.exception('Insufficient quota')
        click.echo('Insufficient quota, please contact us at support@intezer.com ')
    except Exception:
        logger.exception('Unexpected error occurred')
        click.echo('Unexpected error occurred, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}')


@main_cli.command('analyze-by-list', short_help='Send a text file with list of hashes')
@click.argument('path', type=click.Path(exists=True, dir_okay=False))
def analyze_by_list(path):
    """ Send a text file with hashes for analysis in Intezer Platform.

    \b
    PATH: Path to txt file.

    \b
    Examples:
      Send txt file with hashes for analysis:
      $ intezer-cli analyze-by-list ~/files/hashes.txt
    """
    try:
        create_global_api()

        commands.analyze_by_txt_file_command(path=path)
    except click.Abort:
        raise
    except Exception:
        logger.exception('Unexpected error occurred')
        click.echo('Unexpected error occurred, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}')

@main_cli.command('index-by-list', short_help='Send a text file with list of hashes, verdict, family name if malicious')
@click.argument('path', type=click.Path(exists=True, dir_okay=False))
@click.option('--index-as', type=click.Choice(['malicious', 'trusted'], case_sensitive=True))
@click.argument('family_name', required=False, type=click.STRING, default=None)
def index_by_list(path: str, index_as: str, family_name: str):
    """
    Send a text file with hashes for indexing in Intezer Platform.

    \b
    PATH: Path to a txt file with hashes

    \b
    Examples:
      $ intezer-cli index-by-list ~/files/hashes.txt malicious family_name
      \b
    """
    try:
        index_type = sdk_consts.IndexType.from_str(index_as)

        if index_type == sdk_consts.IndexType.MALICIOUS and family_name is None:
            click.echo('family_name is mandatory if the index type is malicious')
            return

        create_global_api()

        commands.index_by_txt_file_command(path=path, index_as=index_as, family_name=family_name)
    except click.Abort:
        raise
    except Exception:
        logger.exception('Unexpected error occurred')
        click.echo('Unexpected error occurred, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}')

@main_cli.command('index', short_help='index a file or a directory')
@click.argument('path', type=click.Path(exists=True))
@click.option('--index-as', type=click.Choice(['malicious', 'trusted'], case_sensitive=True))
@click.argument('family_name', required=False, type=click.STRING, default=None)
@click.option('--ignore-directory-count-limit',
              is_flag=True,
              help='ignore directory count limit ({} files)'.format(default_config.unusual_amount_in_dir))
def index(path: str, index_as: str, family_name: str, ignore_directory_count_limit: bool):
    """ Send a file or a directory for indexing

    \b
    PATH: Path to file or directory to index

    \b
    Examples:
      index a single file:
      $ intezer-cli index ~/files/threat.exe.sample malicious family_name
      \b
      index all files in directory:
      $ intezer-cli index ~/files/files-to-index trusted
    """
    try:
        index_type = sdk_consts.IndexType.from_str(index_as)

        if index_type == sdk_consts.IndexType.MALICIOUS and family_name is None:
            click.echo('family_name is mandatory if the index type is malicious')
            return

        create_global_api()

        if os.path.isfile(path):
            commands.index_file_command(file_path=path, index_as=index_as, family_name=family_name)
        else:
            commands.index_directory_command(directory_path=path,
                                             index_as=index_as,
                                             family_name=family_name,
                                             ignore_directory_count_limit=ignore_directory_count_limit)
    except click.Abort:
        raise
    except Exception:
        logger.exception('Unexpected error occurred')
        click.echo('Unexpected error occurred, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}')


@main_cli.command('upload-endpoint-scan', short_help='upload a directory with offline endpoint scan results')
@click.argument('offline_scan_directory', type=click.Path(exists=True))
@click.option('--force', is_flag=True, default=False, help='Upload scan even if it was already uploaded')
@click.option('--max-concurrent', default=0, type=int, help='Maximum number of concurrent uploads.')
def upload_endpoint_scan(offline_scan_directory: str, force: bool, max_concurrent: int):
    """ Upload a directory with offline endpoint scan results


    OFFLINE_SCAN_DIRECTORY: Path to directory with offline endpoint scan results


    Examples:
      upload a directory with offline endpoint scan results:

      $ intezer-cli upload-endpoint-scan /path/to/endpoint_scan_results
    """
    try:
        create_global_api()
        commands.upload_offline_endpoint_scan(offline_scan_directory=offline_scan_directory,
                                              force=force,
                                              max_concurrent_uploads=max_concurrent)
    except click.Abort:
        raise
    except Exception:
        logger.exception('Unexpected error occurred')
        click.echo('Unexpected error occurred, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}')

@main_cli.command('upload-endpoint-scans-in-directory',
              short_help='upload all subdirectories with offline endpoint scan results')
@click.argument('offline_scans_root_directory', type=click.Path(exists=True))
@click.option('--force', is_flag=True, default=False, help='Upload scans even if they were already uploaded')
@click.option('--max-concurrent', default=0, type=int, help='Maximum number of concurrent uploads.')
def upload_endpoint_scans_in_directory(offline_scans_root_directory: str, force: bool = False, max_concurrent: int = 0):
    """ Upload all subdirectories with offline endpoint scan results


    OFFLINE_SCANS_ROOT_DIRECTORY: Path to root directory containing offline endpoint scan results


    Examples:
      upload a directory with offline endpoint scan results:

      $ intezer-cli upload-endpoint-scans-in-directory /path/to/endpoint_scan_results_root
    """
    try:
        create_global_api()
        commands.upload_multiple_offline_endpoint_scans(offline_scans_root_directory=offline_scans_root_directory,
                                                        force=force,
                                                        max_concurrent_uploads=max_concurrent)
    except click.Abort:
        raise
    except Exception:
        logger.exception('Unexpected error occurred')
        click.echo('Unexpected error occurred, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}')

@main_cli.command('upload-emails-in-directory',
              short_help='upload all subdirectories with .emal files')
@click.argument('emails_root_directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--ignore-directory-count-limit',
              is_flag=True,
              help='ignore directory count limit ({} files)'.format(default_config.unusual_amount_in_dir))
def upload_emails_in_directory(emails_root_directory: str, ignore_directory_count_limit: bool = False):
    """ Upload all subdirectories with .eml files to analyze


    UPLOAD_EMAILS_IN_DIRECTORY: Path to root directory containing the .eml fiels


    Examples:
      upload a directory with .eml files:

      $ intezer-cli upload-emails-in-directory /path/to/emails_root_directory
    """
    try:
        create_global_api()
        commands.send_phishing_emails_from_directory_command(path=emails_root_directory,
                                                             ignore_directory_count_limit=ignore_directory_count_limit)
    except click.Abort:
        raise
    except Exception:
        logger.exception('Unexpected error occurred')
        click.echo('Unexpected error occurred, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}')


@main_cli.group('alerts', short_help='Alert management commands')
def alerts():
    """Alert management commands for Intezer Platform."""
    pass


@main_cli.group('alerts-data-sources', cls=AliasedGroup, short_help='Alert data source connector management')
def alerts_data_sources():
    """Manage alert data source connectors for Intezer Platform."""
    pass


@alerts_data_sources.command('connect', short_help='Connect a new alert data source')
@click.option('--source', required=True, type=click.STRING, help='Alert source type')
@click.option('--name', required=True, type=click.STRING, help='Connector name (must match ^[a-z0-9-]*$)')
@click.option('--config', 'config_file', required=True, type=click.File('r'),
              help='Path to JSON file with source-specific credentials (use - for stdin)')
@click.option('--resolve-false-positive', is_flag=True, default=False,
              help='Enable auto-resolve false positives')
@click.option('--noting', is_flag=True, default=False, help='Enable noting')
@click.option('--auto-endpoint-scan', is_flag=True, default=False, help='Enable auto endpoint scan')
@click.option('--wait', is_flag=True, default=False, help='Poll status until terminal state')
def connect_data_source(source: str, name: str, config_file,
                        resolve_false_positive: bool, noting: bool,
                        auto_endpoint_scan: bool, wait: bool):
    """Connect a new alert data source connector.

    \b
    Examples:
      $ intezer-cli alerts-data-sources connect --source crowdstrike --name acme-corp --config creds.json
      $ intezer-cli alerts-data-sources connect --source crowdstrike --name acme-corp --config - < creds.json
      $ intezer-cli alerts-data-sources connect --source crowdstrike --name acme-corp --config creds.json --wait
    """
    try:
        create_global_api()
        connector_commands.connect_alert_data_source_command(
            source=source,
            name=name,
            config_file=config_file,
            resolve_false_positive=resolve_false_positive,
            noting=noting,
            auto_endpoint_scan=auto_endpoint_scan,
            wait=wait
        )
    except click.Abort:
        raise
    except click.ClickException:
        raise
    except Exception:
        logger.exception('Unexpected error occurred')
        click.echo('Unexpected error occurred, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}', err=True)


@alerts_data_sources.command('connect-batch', short_help='Connect multiple alert data sources from a JSONL file')
@click.option('--config', 'config_file', required=True, type=click.File('r'),
              help='Path to JSONL file (one full connector body per line). Use - for stdin.')
@click.option('--wait', is_flag=True, default=False, help='Poll each connector until terminal state')
@click.option('--max-concurrent', type=click.IntRange(min=1, max=5), default=5, show_default=True,
              help='Maximum number of connectors processed in parallel (capped at 5)')
def connect_data_sources_batch(config_file, wait: bool, max_concurrent: int):
    """Connect multiple alert data source connectors concurrently from a JSONL file.

    \b
    Each line of the file must be a full connector body containing at minimum
    `alert_source` and `connector_name`, plus any source-specific credentials and
    optional feature flags. Any malformed line aborts the whole operation before
    any request is sent.

    \b
    Examples:
      $ intezer-cli alerts-data-sources connect-batch --config connectors.jsonl
      $ intezer-cli alerts-data-sources connect-batch --config - < connectors.jsonl --wait
      $ intezer-cli alerts-data-sources connect-batch --config connectors.jsonl --max-concurrent 10
    """
    try:
        create_global_api()
        connector_commands.connect_alert_data_sources_batch_command(
            config_file=config_file,
            wait=wait,
            max_concurrent=max_concurrent,
        )
    except click.Abort:
        raise
    except click.ClickException:
        raise
    except Exception:
        logger.exception('Unexpected error occurred')
        click.echo('Unexpected error occurred, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}', err=True)


@alerts_data_sources.command('deactivate', short_help='Deactivate a connector')
@click.argument('connector_id', type=click.STRING)
@click.option('--wait', is_flag=True, default=False, help='Poll status until terminal state')
def deactivate_data_source(connector_id: str, wait: bool):
    """Deactivate an alert data source connector.

    \b
    CONNECTOR_ID: The connector ID to deactivate.

    \b
    Examples:
      $ intezer-cli alerts-data-sources deactivate acme-corp
      $ intezer-cli alerts-data-sources deactivate acme-corp --wait
    """
    try:
        create_global_api()
        connector_commands.deactivate_alert_data_source_command(connector_id=connector_id, wait=wait)
    except click.Abort:
        raise
    except click.ClickException:
        raise
    except Exception:
        logger.exception('Unexpected error occurred')
        click.echo('Unexpected error occurred, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}', err=True)


@alerts_data_sources.command('reactivate', short_help='Reactivate a connector')
@click.argument('connector_id', type=click.STRING)
@click.option('--wait', is_flag=True, default=False, help='Poll status until terminal state')
def reactivate_data_source(connector_id: str, wait: bool):
    """Activate (reactivate) an alert data source connector.

    \b
    CONNECTOR_ID: The connector ID to activate.

    \b
    Examples:
      $ intezer-cli alerts-data-sources activate acme-corp
      $ intezer-cli alerts-data-sources activate acme-corp --wait
    """
    try:
        create_global_api()
        connector_commands.reactivate_alert_data_source_command(connector_id=connector_id, wait=wait)
    except click.Abort:
        raise
    except click.ClickException:
        raise
    except Exception:
        logger.exception('Unexpected error occurred')
        click.echo('Unexpected error occurred, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}', err=True)


@alerts_data_sources.command('update', short_help='Update connector credentials or settings')
@click.argument('connector_id', type=click.STRING)
@click.option('--config', 'config_file', required=True, type=click.File('r'),
              help='Path to JSON file with updated credentials or settings (use - for stdin)')
@click.option('--wait', is_flag=True, default=False, help='Poll status until terminal state')
def update_data_source(connector_id: str, config_file, wait: bool):
    """Update an alert data source connector's credentials or settings.

    \b
    CONNECTOR_ID: The connector ID to update.

    \b
    Examples:
      $ intezer-cli alerts-data-sources update <connector-id> --config new-creds.json
      $ intezer-cli alerts-data-sources update <connector-id> --config - < new-creds.json
      $ intezer-cli alerts-data-sources update <connector-id> --config new-creds.json --wait
    """
    try:
        create_global_api()
        connector_commands.update_alert_data_source_command(
            connector_id=connector_id,
            config_file=config_file,
            wait=wait
        )
    except click.Abort:
        raise
    except click.ClickException:
        raise
    except Exception:
        logger.exception('Unexpected error occurred')
        click.echo('Unexpected error occurred, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}', err=True)


@alerts.command('notify-from-csv', short_help='Notify alerts from CSV file')
@click.argument('csv_path', type=click.Path(exists=True, dir_okay=False))
def notify_from_csv(csv_path: str):
    """Notify alerts from a CSV file containing alert IDs and environments.

    \b
    CSV_PATH: Path to CSV file with 'id' and 'environment' columns.

    \b
    CSV Format:
      The CSV file should have the following columns:
      - id: Alert ID (required)
      - environment: Environment name (required)

    \b
    Examples:
      Notify alerts from CSV file:
      $ intezer-cli alerts notify-from-csv ~/alerts.csv
    """
    try:
        create_global_api()
        commands.notify_alerts_from_csv_command(csv_path=csv_path)
    except click.Abort:
        raise
    except Exception:
        logger.exception('Unexpected error occurred')
        click.echo('Unexpected error occurred, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}')

@main_cli.group('subtenants', cls=AliasedGroup, short_help='Subtenants management commands')
def subtenants():
    """Subtenants management commands for Intezer Platform."""
    pass


@subtenants.command('upload-from-csv')
@click.argument('csv_path', type=click.Path(exists=True, dir_okay=False))
@click.option('--skip-dedup', is_flag=True, default=False,
              help='Skip deduplication check against existing subtenants')
def upload_from_csv(csv_path: str, skip_dedup: bool):
    """Upload subtenants from a CSV file.

    \b
    CSV_PATH: Path to CSV file. Header matching is case-insensitive and accepts
    either of the following column names per field:
      - name (required):     'Tenant name' or 'name'
      - account_names:       'Accounts', 'accountNames', or 'account_names'
      - site_names:          'Sites', 'siteNames', or 'site_names'
      - domains:             'domains'
      - environments:        'Envs' or 'environments'
      - tags:                'tags'
    Multi-value cells may use either ',' or '/' as the separator.
    The command fails if two headers map to the same field (e.g. 'sites' and 'site_names').

    \b
    Examples:
      Upload subtenants from CSV file:
      $ intezer-cli subtenants upload-from-csv ~/subtenants.csv
      \b
      Upload without deduplication:
      $ intezer-cli subtenants upload-from-csv ~/subtenants.csv --skip-dedup
    """
    try:
        create_global_api()
        subtenant_commands.upload_subtenants_from_csv_command(csv_path=csv_path, skip_dedup=skip_dedup)
    except click.Abort:
        raise
    except Exception:
        logger.exception('Unexpected error occurred')
        click.echo('Unexpected error occurred, please contact us at support@intezer.com '
                   f'and attach the log file in {utilities.log_file_path}')


if __name__ == '__main__':
    try:
        main_cli()
    except Exception as e:
        logger.exception(f'Unexpected error occurred {e}')
        click.echo('Unexpected error occurred')
