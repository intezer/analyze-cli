import enum


class CodeItemType(object):
    FILE = 'file'
    MEMORY_MODULE = 'memory_module'
    FILELESS_CODE = 'fileless_code'


class AnalysisErrorType(enum.Enum):
    FAILED_TO_OPEN_FILE = 'executable file could not be opened'
    ANALYSIS_CREATION_ERROR = 'analysis could not be created due to server error'
    CLOUD_SERVICE_NOT_AVAILABLE = 'intezer cloud could not be reached'
    FILE_TOO_LARGE = 'file is too large, the maximum file size is 20MB'
    QUOTA_EXCEEDED = 'quota limit exceeded. Contact us for more quota'
    GENERAL_ERROR = 'general error on creating analysis'


class IndexResultType(enum.Enum):
    NOT_SUPPORTED = 'File format not supported'
    SUCCESS = 'success'
    FAILED = 'failed'
