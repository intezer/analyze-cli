import logging
import os

from intezer_analyze_cli.config import default_config as config_

logger = logging.getLogger('intezer_client')


def get_key_file_path(key_file_name):
    if os.name == 'posix':
        return os.path.join(os.path.expanduser('~'), config_.key_dir_name, key_file_name)

    return os.path.join(os.path.expandvars('%APPDATA%'), config_.key_dir_name, key_file_name)


def delete_key(key_file_name):
    current_key = get_stored_key(key_file_name)
    if current_key:
        os.remove(get_key_file_path(key_file_name))


def store_key(key, key_file_name):
    current_key = get_stored_key(key_file_name)
    key_file_path = get_key_file_path(key_file_name)
    if current_key:
        os.remove(key_file_path)
        logger.info('Old key deleted')

    if not os.path.exists(os.path.dirname(key_file_path)):
        os.makedirs(os.path.dirname(key_file_path))

    with open(key_file_path, 'w') as f:
        f.write(key)
    logger.info('Key stored')


def get_stored_key(key_file_name):
    key_file_path = get_key_file_path(key_file_name)
    if not os.path.isfile(key_file_path):
        return None

    with open(get_key_file_path(key_file_name), 'r') as file:
        key = file.read()
        return key


def get_stored_api_key():
    return get_stored_key(config_.key_file_name)


def get_stored_default_url():
    return get_stored_key(config_.url_file_name)


def store_api_key(key):
    store_key(key, config_.key_file_name)


def store_default_url(key):
    store_key(key, config_.url_file_name)


def delete_default_url():
    delete_key(config_.url_file_name)
