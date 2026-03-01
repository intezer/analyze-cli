import json
import os
import re
import time
from http import HTTPStatus

import click
from intezer_sdk import api
from intezer_sdk.api import raise_for_status
from yaspin import yaspin

_CONNECTOR_NAME_PATTERN = re.compile(r'^[a-z0-9-]*$')

_TERMINAL_SUCCESS_STATUSES = {'pending', 'active', 'deactivated'}
_TERMINAL_FAILURE_STATUSES = {'credentials_verification_failed', 'deployment_failed', 'update_failed'}
_POLL_INTERVAL_SECONDS = 5


def _get_extra_params():
    tenant_id = os.environ.get('INTEZER_TENANT_ID')
    if tenant_id:
        return {'tenant_id': tenant_id}
    return {}


def _print_bad_request(response):
    if response.status_code == HTTPStatus.BAD_REQUEST:
        click.echo(json.dumps(response.json(), indent=2), err=True)


def connect_alert_data_source_command(source: str,
                                      name: str,
                                      config_file,
                                      resolve_false_positive: bool,
                                      noting: bool,
                                      auto_endpoint_scan: bool,
                                      wait: bool):
    if not _CONNECTOR_NAME_PATTERN.match(name):
        click.echo('Error: Connector name must match ^[a-z0-9-]*$', err=True)
        raise click.Abort()

    try:
        config_data = json.load(config_file)
    except json.JSONDecodeError as e:
        click.echo(f'Error: Invalid JSON in config file: {e}', err=True)
        raise click.Abort()

    request_body = {
        'alert_source': source,
        'connector_name': name,
        'is_resolve_false_positive_enabled': resolve_false_positive,
        'is_noting_enabled': noting,
        'is_auto_endpoint_scan_enabled': auto_endpoint_scan,
        **_get_extra_params(),
    }
    request_body.update(config_data)

    api_client = api.get_global_api()
    response = api_client.request_with_refresh_expired_access_token(
        method='POST',
        path='/alerts-data-sources/connect',
        data=request_body
    )
    _print_bad_request(response)
    raise_for_status(response)
    result = response.json()
    result_url = result.get('result_url')

    connector_id = result.get('connector_id')
    click.echo(f'Connect request sent for connector "{name}"')

    if wait and result_url:
        _wait_for_connector_status(result_url)

    if connector_id:
        click.echo(f'Connector ID: {connector_id}')


def deactivate_alert_data_source_command(connector_id: str, wait: bool):
    api_client = api.get_global_api()
    extra_params = _get_extra_params()
    response = api_client.request_with_refresh_expired_access_token(
        method='POST',
        path=f'/alerts-data-sources/{connector_id}/deactivate',
        **({'data': extra_params} if extra_params else {})
    )
    _print_bad_request(response)
    raise_for_status(response)
    result = response.json()
    result_url = result.get('result_url')

    click.echo(f'Deactivate request sent for "{connector_id}"')

    if wait and result_url:
        _wait_for_connector_status(result_url)


def reactivate_alert_data_source_command(connector_id: str, wait: bool):
    api_client = api.get_global_api()
    extra_params = _get_extra_params()
    response = api_client.request_with_refresh_expired_access_token(
        method='POST',
        path=f'/alerts-data-sources/{connector_id}/reactivate',
        **({'data': extra_params} if extra_params else {})
    )
    _print_bad_request(response)
    raise_for_status(response)
    result = response.json()
    result_url = result.get('result_url')

    click.echo(f'Activate request sent for "{connector_id}"')

    if wait and result_url:
        _wait_for_connector_status(result_url)


def update_alert_data_source_command(connector_id: str, config_file, wait: bool):
    try:
        config_data = json.load(config_file)
    except json.JSONDecodeError as e:
        click.echo(f'Error: Invalid JSON in config file: {e}', err=True)
        raise click.Abort()

    request_data = {**_get_extra_params(), **config_data}

    api_client = api.get_global_api()
    response = api_client.request_with_refresh_expired_access_token(
        method='PUT',
        path=f'/alerts-data-sources/{connector_id}',
        data=request_data
    )
    _print_bad_request(response)
    raise_for_status(response)

    if response.status_code == HTTPStatus.OK:
        click.echo(f'Update applied for "{connector_id}"')
        return

    result = response.json()
    result_url = result.get('result_url')

    click.echo(f'Update request sent for "{connector_id}"')

    if wait and result_url:
        _wait_for_connector_status(result_url)


def _wait_for_connector_status(result_url: str):
    api_client = api.get_global_api()
    base_url = api_client.base_url.removesuffix('api/').rstrip('/')
    last_status = None

    with yaspin(text='Waiting') as sp:
        while True:
            response = api_client.request_with_refresh_expired_access_token(
                method='GET',
                path=result_url,
                base_url=base_url
            )
            raise_for_status(response, statuses_to_ignore=[HTTPStatus.INTERNAL_SERVER_ERROR])
            result = response.json()
            status = result.get('status')

            if status != last_status:
                sp.write(f'Status: {status}')
                sp.text = f'Waiting ({status})'
                last_status = status

            if status in _TERMINAL_SUCCESS_STATUSES:
                sp.ok('✓')
                click.echo('Operation completed successfully')
                return

            if status in _TERMINAL_FAILURE_STATUSES:
                sp.fail('✗')
                error_detail = result.get('error', '')
                if error_detail:
                    click.echo(f'Error: {error_detail}', err=True)
                raise click.ClickException(f'Operation failed with status: {status}')

            time.sleep(_POLL_INTERVAL_SECONDS)
