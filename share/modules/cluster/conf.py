from clap.common.utils import path_extend
from clap.common.config import Defaults

class ClusterDefaults:
    CLUSTER_REPOSITORY_DIR = path_extend(Defaults.modules_data, 'cluster')
    CLUSTER_SEARCH_PATH = path_extend(Defaults.configs_path, 'clusters')
    CLUSTER_DEFAULT_FLETYPES = ['yaml', 'yml']