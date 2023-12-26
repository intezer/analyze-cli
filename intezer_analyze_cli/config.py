class Config(object):
    def __init__(self):
        # Client
        self.unusual_amount_in_dir = 1000
        self.verify_ssl = True

        # Urls
        self.api_url = 'https://analyze.intezer.com/api/'
        self.api_version = 'v2-0'
        self.file_analyses_tab_name = 'file'
        self.endpoint_analyses_tab_name = 'endpoint'
        self.index_results_tab_name = 'private_index'

        # URLs templates
        self.history_page_url_template = '{system_url}/history?tab={tab_name}'
        self.file_analysis_url_template = '{system_url}/analyses/{analysis_id}'
        self.endpoint_analysis_url_template = '{system_url}/endpoint-analyses/{endpoint_analysis_id}'
        self.phishing_alerts_by_time_template = '{system_url}/alerts/?sources=phishing_emails'

        # Key Store
        self.key_dir_name = '.intezer'
        self.key_file_name = 'key'
        self.url_file_name = 'url'

        # Other
        self.is_cloud = True


default_config = Config()
