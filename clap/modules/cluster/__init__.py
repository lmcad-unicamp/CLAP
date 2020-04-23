from .repository import *
from .commands import *
from .module import *

__module_name__ = "cluster"
__module_description__ = "Create and manages compute clusters"
__module_dependencies__ = ['node', 'tag', 'group']