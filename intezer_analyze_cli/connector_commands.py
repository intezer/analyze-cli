import concurrent.futures
import contextlib
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
_BATCH_DEFAULT_MAX_CONCURRENT = 5


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
        **config_data,
    }

    _connect_one(request_body, wait=wait, silent=False)


def connect_alert_data_sources_batch_command(config_file,
                                             wait: bool,
                                             max_concurrent: int = _BATCH_DEFAULT_MAX_CONCURRENT):
    request_bodies = _parse_jsonl_connectors_strict(config_file.read())

    failures: list[tuple[str, str]] = []
    successes: list[tuple[str, str | None]] = []

    label = f'Connecting {len(request_bodies)} connectors'
    with click.progressbar(length=len(request_bodies), label=label) as bar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_name = {
                executor.submit(_connect_one, body, wait, True): body['connector_name']
                for body in request_bodies
            }
            for future in concurrent.futures.as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    successes.append((name, future.result()))
                except Exception as exc:
                    failures.append((name, str(exc)))
                bar.update(1)

    for name, connector_id in successes:
        suffix = f' (id: {connector_id})' if connector_id else ''
        click.echo(f'  ✓ {name}{suffix}')
    for name, error in failures:
        click.echo(f'  ✗ {name}: {error}', err=True)

    if failures:
        raise click.ClickException(
            f'{len(failures)} of {len(request_bodies)} connectors failed'
        )

    click.echo(f'All {len(request_bodies)} connectors processed successfully')


def _parse_jsonl_connectors_strict(content: str) -> list[dict]:
    entries: list[dict] = []
    for line_no, raw in enumerate(content.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            click.echo(f'Error: invalid JSON on line {line_no}: {e}', err=True)
            raise click.Abort()
        if not isinstance(entry, dict):
            click.echo(f'Error: line {line_no} is not a JSON object', err=True)
            raise click.Abort()
        entry_source = entry.get('alert_source')
        entry_name = entry.get('connector_name')
        if not entry_source or not entry_name:
            click.echo(
                f'Error: line {line_no} must include "alert_source" and "connector_name"',
                err=True
            )
            raise click.Abort()
        if not _CONNECTOR_NAME_PATTERN.match(entry_name):
            click.echo(
                f'Error: connector name "{entry_name}" on line {line_no} must match ^[a-z0-9-]*$',
                err=True
            )
            raise click.Abort()
        entries.append(entry)

    if not entries:
        click.echo('Error: config file contains no connector entries', err=True)
        raise click.Abort()
    return entries


def _connect_one(request_body: dict, wait: bool, silent: bool = False) -> str | None:
    body = {**request_body, **_get_extra_params()}
    name = body.get('connector_name')

    api_client = api.get_global_api()
    response = api_client.request_with_refresh_expired_access_token(
        method='POST',
        path='/alerts-data-sources/connect',
        data=body
    )
    if silent and response.status_code == HTTPStatus.BAD_REQUEST:
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        raise click.ClickException(f'bad request: {payload}')
    if not silent:
        _print_bad_request(response)
    raise_for_status(response)
    result = response.json()
    result_url = result.get('result_url')
    connector_id = result.get('connector_id')

    if not silent:
        click.echo(f'Connect request sent for connector "{name}"')

    if wait and result_url:
        _wait_for_connector_status(result_url, silent=silent)

    if connector_id and not silent:
        click.echo(f'Connector ID: {connector_id}')

    return connector_id


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


@contextlib.contextmanager
def _maybe_spinner(silent: bool):
    if silent:
        yield None
    else:
        with yaspin(text='Waiting') as sp:
            yield sp


def _wait_for_connector_status(result_url: str, silent: bool = False):
    api_client = api.get_global_api()
    base_url = api_client.base_url.removesuffix('api/').rstrip('/')
    last_status = None

    with _maybe_spinner(silent) as sp:
        while True:
            response = api_client.request_with_refresh_expired_access_token(
                method='GET',
                path=result_url,
                base_url=base_url
            )
            raise_for_status(response, statuses_to_ignore=[HTTPStatus.INTERNAL_SERVER_ERROR])
            result = response.json()
            status = result.get('status')

            if not silent and status != last_status:
                sp.write(f'Status: {status}')
                sp.text = f'Waiting ({status})'
                last_status = status

            if status in _TERMINAL_SUCCESS_STATUSES:
                if not silent:
                    sp.ok('✓')
                    click.echo('Operation completed successfully')
                return

            if status in _TERMINAL_FAILURE_STATUSES:
                error_detail = result.get('error', '')
                if not silent:
                    sp.fail('✗')
                    if error_detail:
                        click.echo(f'Error: {error_detail}', err=True)
                message = f'Operation failed with status: {status}'
                if silent and error_detail:
                    message = f'{message}: {error_detail}'
                raise click.ClickException(message)

            time.sleep(_POLL_INTERVAL_SECONDS)
