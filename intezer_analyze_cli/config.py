class Config(object):
    def __init__(self):
        # Client
        self.unusual_amount_in_dir = 1000

        # Urls
        self.api_url = 'https://analyze.intezer.com/api/'
        self.api_version = 'v2-0'
        self.analyses_url = 'https://analyze.intezer.com/analyses'
        self.index_results_url = 'https://analyze.intezer.com/private-indexed-files'

        # Key Store
        self.key_dir_name = '.intezer'
        self.key_file_name = 'key'
        self.url_file_name = 'url'

        # Other
        self.is_cloud = True


default_config = Config()
