import click
import yaml
from collections import defaultdict
from dataclasses import asdict
from clap.node_manager import NodeRepositoryController
from clap.repository import RepositoryFactory
from clap.role_manager import RoleManager, NodeRoleError
from clap.utils import path_extend, get_logger, Singleton, defaultdict_to_dict
from app.cli.cliapp import clap_command, Defaults, ArgumentError

logger = get_logger(__name__)


class RoleDefaults(metaclass=Singleton):
    def __init__(self):
        self.base_defaults = Defaults()
        self.role_dir = path_extend(self.base_defaults.clap_path, 'roles')
        self.actions_dir = path_extend(self.role_dir, 'actions.d')
        self.repository_type = 'sqlite'
        self.node_repository_path = path_extend(
            self.base_defaults.storage_path, 'nodes.db')


role_defaults = RoleDefaults()


def get_role_manager() -> RoleManager:
    repository = RepositoryFactory().get_repository(
        role_defaults.repository_type, role_defaults.node_repository_path,
        verbosity=role_defaults.base_defaults.verbosity)
    node_repository = NodeRepositoryController(repository)
    role_manager = RoleManager(
        node_repository, role_defaults.role_dir, role_defaults.actions_dir,
        role_defaults.base_defaults.private_path
    )
    return role_manager


def _split_vars(nodes, node_vars, host_vars, extra_vars):
    # Preprocess node
    # Is format <role_host_name>:<node>,<node>, ...?
    if nodes:
        if all(':' in n for n in nodes):
            _nodes = defaultdict(list)
            for n in nodes:
                host_name, list_nodes = n.split(':')
                _nodes[host_name] += [n for n in list_nodes.split(',') if n]
            _nodes = dict(_nodes)
        # Is format <node>,<node>  <node>,<node>
        elif all(':' not in n for n in nodes):
            _nodes = [h for n in nodes for h in n.split(',') if h]
        else:
            raise ValueError('Multiple formats for node option. Specify a host or '
                             'not for all node options')
    else:
        _nodes = []

    # Preprocess node extra args
    node_variables = defaultdict(dict)
    for nvar in node_vars:
        if ':' not in nvar:
            raise ValueError(f"Invalid value for node argument: `{nvar}`. "
                             f"Did you forgot ':' character?")
        node_id, node_extra_args = nvar.split(':')[0], ':'.join(nvar.split(':')[1:])
        for narg in node_extra_args.split(','):
            if '=' not in narg:
                raise ValueError(f"Invalid value for extra argument: '{narg}'. "
                                 f"Did you forgot '=' character?")
            extra_name, extra_value = narg.split('=')[0], '='.join(narg.split('=')[1:])
            node_variables[node_id].update({extra_name: extra_value})

    # Preprocess host extra args
    host_variables = defaultdict(dict)
    for hvar in host_vars:
        if ':' not in hvar:
            raise ValueError(f"Invalid value for host argument: `{hvar}`. "
                             f"Did you forgot ':' character?")
        host, host_extras = hvar.split(':')[0], ':'.join(hvar.split(':')[1:])
        for harg in host_extras.split(','):
            if '=' not in harg:
                raise ValueError(f"Invalid value for host extra argument: '{harg}'. "
                                 f"Did you forgot '=' character?")
            extra_name, extra_value = harg.split('=')[0], '='.join(harg.split('=')[1:])
            host_variables[host].update({extra_name: extra_value})

    # Preprocess extra args
    extra_args = dict()
    for e in extra_vars:
        if '=' not in e:
            raise ValueError(f"Invalid value for extra argument: `{e}`. "
                             f"Did you forgot '=' character?")
        extra_name, extra_value = e.split('=')[0], '='.join(e.split('=')[1:])
        extra_args[extra_name] = extra_value

    node_variables = defaultdict_to_dict(node_variables)
    host_variables = defaultdict_to_dict(host_variables)
    return _nodes, node_variables, host_variables, extra_args


@clap_command
@click.group(help='Control and manage roles')
@click.option('-r', '--roles-root', default=role_defaults.role_dir,
              help='Path where roles will be searched for', show_default=True)
@click.option('-n', '--node-repository', default=role_defaults.node_repository_path,
              help='Node database where nodes will be written', show_default=True)
def role(roles_root, node_repository):
    role_defaults.role_dir = roles_root
    role_defaults.node_repository_path = node_repository


@role.command('add')
@click.argument('role', nargs=1, type=str, required=True)
@click.argument('nodes', nargs=-1, type=str, required=False)
@click.option('-n', '--node', nargs=1, type=str, required=False, multiple=True,
              help='Nodes to be added. Can use multiple "-n" commands and it '
                   'can be a list of colon-separated nodes as "<node>,<node>,..." '
                   'or "<role_host_name>:<node>,<node>". The formats are '
                   'mutually exclusive')
@click.option('-nv', '--node-vars', multiple=True,
              help="Node's arguments. Format <node_id>:<key>=<value>,<key>=<val>")
@click.option('-hv', '--host-vars', multiple=True,
              help="Role's host arguments. Format <host_name>:<key>=<value>,...")
@click.option('-e', '--extra', multiple=True,
              help='Extra arguments. Format <key>=<value>')
def role_add(role, nodes, node, node_vars, host_vars, extra):
    """ Add a set of nodes to a role.

    The ROLE argument specify the role which the nodes will be added.
    """
    role_manager = get_role_manager()
    node += nodes
    nodes, node_vars, host_vars, extra_args = _split_vars(
        node, node_vars, host_vars, extra)
    if not nodes:
        raise ArgumentError('No nodes informed')

    added_nodes = role_manager.add_role(
        role, hosts_node_map=nodes, host_vars=host_vars,
        node_vars=node_vars, extra_args=extra_args)

    print(f"{len(added_nodes)} nodes were added to role {role}: {', '.join(sorted(added_nodes))}")
    return 0


@role.command('action')
@click.argument('role', nargs=1, type=str, required=True)
@click.option('-a', '--action', nargs=1, type=str, required=True,
              help="Name of the group's action to perform")
@click.argument('nodes', nargs=-1, type=str, required=False)
@click.option('-n', '--node', nargs=1, type=str, multiple=True, required=False,
              help='Nodes to perform the action. Can use multiple "-n" commands and it '
                   'can be a list of colon-separated node as "<node>,<node>,..." '
                   'or "<role_host_name>:<node>,<node>". The formats are '
                   'mutually exclusive. If not is passed, the action will be '
                   'performed in all nodes that belongs to the role.')
@click.option('-nv', '--node-vars', multiple=True,
              help="Node's arguments. Format <node_id>:<key>=<value>,<key>=<val>")
@click.option('-hv', '--host-vars', multiple=True,
              help="Role's host arguments. Format <host_name>:<key>=<value>,...")
@click.option('-e', '--extra', multiple=True,
              help='Extra arguments. Format <key>=<value>')
def role_action(role, action, nodes, node, node_vars, host_vars, extra):
    """ Perform an group action at a set of nodes.

    The ROLE argument specify the role which the action will be performed.
    """
    role_manager = get_role_manager()
    node += nodes
    nodes, node_vars, host_vars, extra_args = _split_vars(
        node, node_vars, host_vars, extra)

    if not nodes:
        nodes = role_manager.get_all_role_nodes_hosts(role)
    else:
        if type(nodes) is list:
            d = defaultdict(list)
            for n in nodes:
                hosts = role_manager.get_role_node_hosts(role, n)
                if not hosts:
                    raise NodeRoleError(n, role)
                for hname in hosts:
                    d[hname].append(n)
            nodes = defaultdict_to_dict(d)
        else:
            nodes = nodes

    all_values = [n for v in nodes.values() for n in v]
    if not all_values:
        raise ValueError(f"No nodes to perform the action '{action} of role {role}")

    result = role_manager.perform_action(
        role, action, hosts_node_map=nodes, host_vars=host_vars,
        node_vars=node_vars, extra_args=extra_args)

    if not result.ok:
        logger.error(f"Playbook for action {action} of role {role} did not "
                     f"executed successfully...")
        return 1

    print(f"Action {action} from role {role} was successfully performed!")
    return 0


@role.command('remove')
@click.argument('role', nargs=1, type=str, required=True)
@click.argument('nodes', nargs=-1, type=str, required=False)
@click.option('-n', '--node', nargs=1, type=str, multiple=True, required=False,
              help='Nodes to perform the action. Can use multiple "-n" commands and it '
                   'can be a list of colon-separated node as "<node>,<node>,..." '
                   'or "<role_host_name>:<node>,<node>". The formats are '
                   'mutually exclusive. If not is passed, the action will be '
                   'performed in all nodes that belongs to the role.')
def role_remove(role, nodes, node):
    """ Perform an group action at a set of nodes.

    The ROLE argument specify the role which the action will be performed.
    """
    role_manager = get_role_manager()
    node += nodes
    nodes, node_vars, host_vars, extra_args = _split_vars(node, [], [], [])

    if not nodes:
        raise ArgumentError('No nodes informed')

    if type(nodes) is list:
        d = defaultdict(list)
        for n in nodes:
            hosts = role_manager.get_role_node_hosts(role, n)
            if not hosts:
                raise NodeRoleError(n, role)
            for hname in hosts:
                d[hname].append(n)
        nodes = defaultdict_to_dict(d)
    else:
        nodes = nodes

    if not nodes:
        raise ValueError(f"No nodes to remove from role {role}")

    result = role_manager.remove_role(role, nodes)
    print(f"{len(result)} nodes were removed from {role}: {', '.join(sorted(result))}")
    return 0


@role.command('list')
@click.argument('role', nargs=-1, type=str)
@click.option('-d', '--detailed', help='Show detailed role information',
              is_flag=True, default=False, show_default=True)
@click.option('-i', '--indent', default=4, show_default=True, nargs=1,
              type=int, help="Indentation level")
@click.option('-q', '--quiet', default=False, is_flag=True, show_default=True,
              help="Show only template ids")
def role_list(role, detailed, indent, quiet):
    """Print roles in role path.

    The ROLE argument filter specific roles.
    """
    if quiet and detailed:
        raise ValueError(f"Options `detailed` and `quiet` are mutually exclusive")

    role_manager = get_role_manager()
    roles = role_manager.roles if not role else {
        rname: r
        for rname, r in role_manager.roles.items() if rname in role
    }

    for role_name in sorted(roles.keys()):
        if quiet:
            print(role_name)
            continue

        role_info = roles[role_name]
        if not detailed:
            print(f"* name: {role_name}")
            print(f"  Has {len(role_info.actions)} actions and "
                  f"{len(role_info.hosts)} hosts defined")
            print(f"    actions: {', '.join(sorted(role_info.actions.keys()))}")
            print(f"    hosts: {', '.join(sorted(role_info.hosts))}")
        else:
            print(f"{'-' * 20} ROLE: `{role_name}` {'-' * 20}")
            print(f"{yaml.dump(asdict(role_info), sort_keys=True, indent=indent)}")
            print(f"{'-' * 80}")

        print()

    if not quiet:
        print(f"Listed {len(roles)} roles")
    return 0
