import csv
import logging
import os
import tempfile
import zipfile

import click

log_file_path = ''


def get_log_record_extra_fields(record):
    """Taken from `common` repo logging module"""
    # The list contains all the attributes listed in
    # http://docs.python.org/library/logging.html#logrecord-attributes
    skip_list = (
        'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
        'funcName', 'id', 'levelname', 'levelno', 'lineno', 'module',
        'msecs', 'msecs', 'message', 'msg', 'name', 'pathname', 'process',
        'processName', 'relativeCreated', 'thread', 'threadName', 'extra',
        'stack_info', 'exc_type', 'exc_msg')

    easy_types = (str, bool, dict, float, int, list, type(None))

    fields = {}

    for key, value in record.__dict__.items():
        if key not in skip_list:
            if isinstance(value, easy_types):
                fields[key] = value
            else:
                fields[key] = repr(value)

    return fields


class ExtraFormatter(logging.Formatter):
    """Taken from `common` repo logging module"""

    def format(self, record):
        extra = get_log_record_extra_fields(record)

        if extra:
            extra_string = \
                ', '.join(['{}: {}'.format(field, value) for field, value in sorted(extra.items())])
        else:
            extra_string = ''

        record.__dict__['extra'] = extra_string

        return super(ExtraFormatter, self).format(record)


def init_log(logger_name, debug_mode=False):
    global log_file_path
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # file
    try:
        tempdir = tempfile.mkdtemp('intezer-logs')
        log_file_path = os.path.join(tempdir, 'intezer-analyze.log')
        handler = logging.FileHandler(log_file_path)
        formatter = \
            ExtraFormatter('%(asctime)s %(levelname)-8s %(module)s line: %(lineno)d: %(message)s. %(extra)s')

    except Exception:
        print('Failed to create logs directory, prints all logs to the screen')
        handler = logging.StreamHandler()
        formatter = ExtraFormatter('%(levelname)s %(message)s. %(extra)s', '%H:%M:%S')

    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    # stderr
    if debug_mode and handler is not logging.StreamHandler:
        console_formatter = ExtraFormatter('%(levelname)s %(message)s. %(extra)s', '%H:%M:%S')
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.DEBUG)
        logger.addHandler(console_handler)


def is_supported_file(file_path):
    try:
        with open(file_path, 'rb') as f:
            byte = f.read(6)
            is_supported = (byte[:2] == b'MZ' or  # PE
                            byte[:4] == b'\x7fELF' or  # ELF
                            byte[:4] == b'dex\x0a' or  # Dex
                            byte[:4] == b'\x50\x4b\x03\x04' or  # Zip
                            byte[:3] == b'\x1f\x8b\x08' or  # Zip
                            byte[:6] == b'\x37\x7a\xbc\xaf\x27\x1c')  # 7-Zip
    except IOError:
        logging.info('No read permissions for file', extra=dict(file_path=file_path))
        return False

    if not is_supported and zipfile.is_zipfile(file_path):
        is_supported = is_apk(file_path)

    return is_supported


def is_apk(file_path):
    try:
        with zipfile.ZipFile(file_path) as apk_zip:
            file_contents = apk_zip.namelist()
            return ('AndroidManifest.xml' in file_contents and
                    ('classes.dex' in file_contents or 'resources.arsc' in file_contents))
    except (OSError, zipfile.BadZipFile):
        logging.info('Error bad zip file')
        return False


def check_should_continue_for_large_dir(num_of_items, threshold):
    """
    Checks if there is an unusual amount of files in the directory, if so, asks the user if he's sure that he wants
    to continue. If the answer is no, aborting the operation
    :param num_of_items: The number of items in the dir
    :param threshold: The threshold amount required to do the check
    """
    if num_of_items <= threshold:
        return

    click.confirm('This directory contains more than {} files, are you sure you want to continue?'.format(threshold),
                  abort=True)


def indexes_list_to_csv(csv_path, indexes_list):
    file_path = os.path.join(csv_path, 'result.csv')
    with open(file_path, 'w') as csvFile:
        writer = csv.DictWriter(csvFile, fieldnames=['file_name', 'result'])
        writer.writeheader()
        writer.writerows(indexes_list)

    csvFile.close()


def export_to_csv(csv_file_path, items, keys=None):
    if not keys:
        keys = {key for code_item_data in items for key in code_item_data.keys()}

    sorted_keys = sorted(keys)

    with open(csv_file_path, 'w') as output_file:
        dict_writer = csv.DictWriter(output_file, sorted_keys)
        dict_writer.writeheader()
        dict_writer.writerows(items)


def is_hidden(path):
    if os.name == 'nt':
        try:
            import win32api
            import win32con
        except ImportError:
            return False
        attribute = win32api.GetFileAttributes(path)
        return attribute & (win32con.FILE_ATTRIBUTE_HIDDEN | win32con.FILE_ATTRIBUTE_SYSTEM)
    else:
        return os.path.basename(path).startswith('.')


if __name__ == '__main__':
    is_supported_file('/home/david/Downloads/lsass_pe.7z')
