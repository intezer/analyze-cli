class Config(object):
    def __init__(self):
        # Client
        self.unusual_amount_in_dir = 1000

        # Urls
        self.api_url = 'https://analyze.intezer.com/api/'
        self.api_version = 'v2-0'
        self.analyses_url = 'https://analyze.intezer.com/#/analyses'

        # Cloud Service
        self.max_upload_file_size = 20 * 1024 * 1024

        # Key Store
        self.key_dir_name = '.intezer'
        self.key_file_name = 'key'
        self.url_file_name = 'url'

        # Other
        self.is_cloud = True


default_config = Config()
