from .commands import *
from .module import *
from .repository import *
from .conf import ClusterDefaults

__module_name__ = "cluster"
__module_description__ = "Create and manages compute clusters"
__module_dependencies__ = ['node', 'tag', 'group', 'template']