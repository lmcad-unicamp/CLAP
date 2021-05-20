from typing import List, Dict, Any

from common.abstract_provider import AbstractModule
from common.utils import get_logger
from modules.group import GroupModule

logger = get_logger(__name__)


class SpitsModule(AbstractModule):
    @staticmethod
    def get_module(**defaults_override) -> 'SpitsModule':
        group_module = GroupModule.get_module()
        return SpitsModule(group_module)

    def __init__(self, group_module: GroupModule):
        self.group_module = group_module
        if 'spits' not in self.group_module.list_groups():
            raise Exception("Group spits does not exists")

    def query_job_status(self, jobid: str, node_ids: List[str], pypits_path: str = None, spits_job_path: str = None, quiet: bool = False) -> Dict[str, Any]:
        extra = {'jobid': jobid}
        if pypits_path:
            extra['PYPITS_PATH'] = pypits_path
        if spits_job_path:
            extra['SPITS_JOB_PATH'] = spits_job_path

        logger.info(f"Querying status of job `{jobid}`...")
        result = self.group_module.execute_group_action(group_name='spits', action_name='job-status',
                                                        node_ids=node_ids, extra_args=extra, quiet=quiet)
        if not result.ok:
            raise Exception("Playbook did not execute correctly")

        return result.vars
