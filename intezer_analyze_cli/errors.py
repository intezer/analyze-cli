import sys


def with_extra(exception=None, **kwargs):
    if not exception:
        exception = sys.exc_info()[1]

    nested_extra = kwargs.get('extra')
    if nested_extra and isinstance(nested_extra, dict):
        extra = nested_extra
    else:
        extra = kwargs

    if hasattr(exception, 'extra'):
        exception.extra.update(extra)
    else:
        exception.extra = extra

    return exception


class IntezerException(Exception):
    pass


class UploadedFileTooLargeError(IntezerException):
    def __init__(self, file_size):
        self.file_size = file_size


class InvalidKeyError(IntezerException):
    def __init__(self, key):
        self.key = key


class CloudServiceNotAvailableError(IntezerException):
    def __init__(self, message=None):
        super(IntezerException, self).__init__(message)


class AnalysisCreationError(IntezerException):
    def __init__(self, message=None):
        super(IntezerException, self).__init__(message)


class QuotaLimitReachedError(IntezerException):
    def __init__(self, message=None):
        super(IntezerException, self).__init__(message)
