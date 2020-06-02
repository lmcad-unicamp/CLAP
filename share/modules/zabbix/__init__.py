from .commands import *
from .module import *

__module_name__ = "zabbix"
__module_description__ = "Manage and perform operation with zabbix nodes"
__module_dependencies__ = ['tag', 'group', 'node']