from clap.common.utils import path_extend
from clap.common.config import Defaults

class ParamountClusterDefaults:
    PARAMOUNT_CLUSTER_REPOSITORY_DIR = path_extend(Defaults.modules_data, 'paramount-cluster')

class ParamountState:
    NOT_RUN='not run'
    RUNNING='running'
    ERROR='error'
    SOME_ERROR='some errors'
    TERMINATED='terminated'