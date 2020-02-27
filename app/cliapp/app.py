import logging
import time
import traceback
import sys
import argparse

from typing import List

from app.cliapp.commands import print_all_help, get_commands_parser
from clap.common.commands import AbstractParser
from clap.common.config import Defaults
from clap.common.utils import log, setup_log
from clap.common.factory import PlatformFactory

# cluster create [driver_id] <cluster_template_path>
# cluster list [tags]
# cluster check <cluster_ids>
# cluster show <cluster_ids>
# cluster stop <cluster_ids>

# node start <cluster_id> <node_type>:<qtde>[, <node_type>:<qtde> ...]
# node list [cluster_id] [tags]
# node show <node_ids>
# node alive <node_ids>
# node stop <node_ids>
# node playbook <playbook> <node_ids> [kwargs]
# node connect [opts] <node_id>

# module show-all <-- Implementations of ABSModule
# module list [cluster] [node] [name] [tags]
# module show <module_ids>

# spits install <node_ids> [kwargs]
# spits check <module_ids> [kwargs]
# spits uninstall <module_ids> [kwargs]
# spits job-create <jobid> <job_config> [kwargs]
# spits job-list [modules]
# spits job-show <job_ids>
# spits job-status <job_ids>
# spits job-copy-back <jobid> [node_ids] [kwargs] (default is JM node)
# spits job-stop <job_id> [kwargs]
# spits process-start-jm <job_id> <node_id> [kwargs]
# spits process-start-tm <job_id> <node_id> [kwargs]
# spits process-list [manager_type] [jobid] [node_id]
# spits process-show <process_ids>
# spits process-alive <process_id>
# spits process-terminate <process_id> [kwargs]
# spits worker-list <jm_process_id>
# spits worker-add <jm_process_id> <tm_process_id>
# spits worker-remove <jm_process_id> <tm_process_id>
# spits metrics-list <process_ids>
# spits metrics-last-values <process_id> <metric1> [<metrics>]
# spits metrics-last-history <process_id> <metric1>:<val> [<metrics>:<val>]


def main(arguments: List[str]):
    parser, commands_parser = get_commands_parser()
    module_iface = PlatformFactory.get_module_interface()
    for module in module_iface.get_modules():
        if 'parser' in module.__dict__ and module.parser is not None and issubclass(module.parser, AbstractParser):
            commands_com_parser = commands_parser.add_parser(module.name, help=module.description)
            commands_subcom_parser = commands_com_parser.add_subparsers(title='commands', dest='subcommand')
            module.parser().get_parser(commands_subcom_parser)

    try:
        args = parser.parse_args(arguments)
        setup_log(Defaults.app_name, args.verbose)

    except Exception as err:
        log.error("Parsing command line arguments: {}".format(err))
        return 1

    log.debug("""CLAP start at: {}
{}
Using paths:
  in-use driver = {}
  platform repository file = {}
  repository type = {}
  private path = {}
  storage path = {}
  configs path = {}
  groups path = {}
  modules path = {}
  (driver) elasticluster storage = {}
  verbosity level = {}
{}
""".format(
        time.ctime(), '-' * 80, args.driver, args.platform_db, args.repo_type, Defaults.private_path,
        Defaults.storage_path, Defaults.configs_path, Defaults.groups_path, Defaults.modules_path,
        Defaults.elasticluster_storage_path, args.verbose, '-' * 80))

    if args.show_all_help is True:
        print_all_help(parser)
        return 0

    if not args.command:
        log.error("Command is required!")
        return 1

    try:
        func = args.func
    except Exception:
        print('Use `{} {} --help` for help about the command'.format(sys.argv[0], ' '.join(arguments)))
        return 1

    # Run function!
    try:
        return args.func(args)
    except Exception as e:
        if args.verbose >= 2:
            traceback.print_exc()

        log.error("{}: {}".format(e.__class__.__name__, e))
        # log.error("Error executing `{} {}`".format(sys.argv[0], ' '.join(arguments)))
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
