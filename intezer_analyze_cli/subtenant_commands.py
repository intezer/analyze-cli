import csv
import logging
import os
import re

import click
from intezer_sdk import api
from intezer_sdk.api import raise_for_status

logger = logging.getLogger('intezer_cli')

_BATCH_SIZE = 5

_FIELD_HEADER_ALIASES = {
    'name': ('tenant name', 'name'),
    'account_names': ('accounts', 'accountnames', 'account_names'),
    'site_names': ('sites', 'sitenames', 'site_names'),
    'domains': ('domains',),
    'environments': ('envs', 'environments'),
    'tags': ('tags',),
}

_VALUE_SEPARATORS = re.compile(r'[,/]')


def _get_extra_params():
    tenant_id = os.environ.get('INTEZER_TENANT_ID')
    if tenant_id:
        return {'tenant_id': tenant_id}
    return {}


def _map_csv_headers_to_api_fields(fieldnames: list[str]) -> dict[str, str]:
    field_to_header = {}
    for api_field, aliases in _FIELD_HEADER_ALIASES.items():
        matching_headers = [header for header in fieldnames
                            if header and header.strip().lower() in aliases]
        if len(matching_headers) > 1:
            raise ValueError(
                f'CSV file has conflicting headers for "{api_field}": '
                f'{", ".join(matching_headers)}'
            )
        if matching_headers:
            field_to_header[api_field] = matching_headers[0]
    return field_to_header


def _read_subtenants_from_csv(csv_path: str) -> list[dict]:
    subtenants = []

    with open(csv_path, 'r', newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)

        if not reader.fieldnames:
            raise ValueError('CSV file is empty')

        field_to_header = _map_csv_headers_to_api_fields(list(reader.fieldnames))

        if 'name' not in field_to_header:
            raise ValueError('CSV file must contain a "Tenant name" or "name" column')

        name_header = field_to_header['name']

        for row in reader:
            name = row[name_header].strip()
            if not name:
                continue

            subtenant = {'name': name}

            for api_field in ('account_names', 'site_names', 'domains', 'environments', 'tags'):
                csv_header = field_to_header.get(api_field)
                if not csv_header:
                    continue
                value = row.get(csv_header, '').strip()
                if value:
                    subtenant[api_field] = [item.strip() for item in _VALUE_SEPARATORS.split(value)
                                            if item.strip()]

            subtenants.append(subtenant)

    if not subtenants:
        raise ValueError('No valid subtenant data found in CSV file')

    return subtenants


def _fetch_existing_subtenants() -> list[dict]:
    api_client = api.get_global_api()
    extra_params = _get_extra_params()
    response = api_client.request_with_refresh_expired_access_token(
        method='GET',
        path='/subtenants',
        **({'params': extra_params} if extra_params else {})
    )
    raise_for_status(response)
    return response.json()['result']


def _filter_duplicates(new_subtenants: list[dict], existing_subtenants: list[dict]) -> tuple[list[dict], int]:
    existing_names = {existing['name'].lower() for existing in existing_subtenants}

    existing_values = {}
    for field in ('account_names', 'site_names', 'domains', 'environments', 'tags'):
        values = set()
        for existing in existing_subtenants:
            for value in existing.get(field, []):
                values.add(value.lower())
        existing_values[field] = values

    filtered = []
    skipped = 0

    for subtenant in new_subtenants:
        if subtenant['name'].lower() in existing_names:
            skipped += 1
            continue

        is_duplicate = False
        for field in ('account_names', 'site_names', 'domains', 'environments', 'tags'):
            for value in subtenant.get(field, []):
                if value.lower() in existing_values[field]:
                    is_duplicate = True
                    break
            if is_duplicate:
                break

        if is_duplicate:
            skipped += 1
        else:
            filtered.append(subtenant)

    return filtered, skipped


def _create_subtenants_batch(batch: list[dict]):
    api_client = api.get_global_api()
    request_data = {'subtenants': batch, **_get_extra_params()}
    response = api_client.request_with_refresh_expired_access_token(
        method='POST',
        path='/subtenants',
        data=request_data
    )
    raise_for_status(response)


def upload_subtenants_from_csv_command(csv_path: str, skip_dedup: bool = False):
    try:
        subtenants = _read_subtenants_from_csv(csv_path)
        skipped = 0

        if not skip_dedup:
            existing = _fetch_existing_subtenants()
            subtenants, skipped = _filter_duplicates(subtenants, existing)

        if not subtenants:
            click.echo(f'No new subtenants to create ({skipped} skipped as duplicates)')
            return

        created = 0
        failed = 0

        batches = [subtenants[i:i + _BATCH_SIZE] for i in range(0, len(subtenants), _BATCH_SIZE)]

        with click.progressbar(length=len(subtenants),
                               label='Creating subtenants',
                               show_pos=True,
                               width=0) as progressbar:
            for batch in batches:
                try:
                    _create_subtenants_batch(batch)
                    created += len(batch)
                except Exception:
                    logger.exception('Error creating subtenant batch')
                    failed += len(batch)
                progressbar.update(len(batch))

        click.echo(f'{created} subtenants created')
        if skipped > 0:
            click.echo(f'{skipped} subtenants skipped as duplicates')
        if failed > 0:
            click.echo(f'{failed} subtenants failed to create')

    except IOError:
        click.echo(f'No read permissions for {csv_path}')
        logger.exception('Error reading CSV file', extra=dict(path=csv_path))
        raise click.Abort()
    except ValueError as error:
        click.echo(str(error))
        logger.exception('Error parsing CSV file', extra=dict(path=csv_path))
        raise click.Abort()
