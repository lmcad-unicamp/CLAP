import marshmallow as m
import yaml

from marshmallow_dataclass import class_schema
from dataclasses import field, dataclass, asdict
from typing import List, Union, Optional, Dict, Tuple
from marshmallow.validate import Range, Equal
from jinja2 import Template

from common.utils import get_logger
from test.common.fixtures import assertDictEqual

logger = get_logger(__name__)


class InvalidClusterConfiguration(Exception):
    pass


class InvalidSetupConfiguration(Exception):
    pass


@dataclass
class GroupActionType:
    type: str = field(metadata={"validate": Equal("action")})
    name: Optional[str]
    group: Optional[str]
    extra: Optional[Dict[str, str]] = field(default_factory=dict)


@dataclass
class CommandActionType:
    type: str = field(metadata={"validate": Equal("command")})
    command: Optional[str]


@dataclass
class PlaybookActionType:
    type: str = field(metadata={"validate": Equal("playbook")})
    path: Optional[str]
    extra: Optional[Dict[str, str]] = field(default_factory=dict)


@dataclass
class GroupTypeSchema:
    name: str
    extra: Optional[Dict[str, str]] = field(default_factory=dict)


@dataclass
class SetupConfig:
    actions: Optional[List[Union[GroupActionType, CommandActionType, PlaybookActionType]]] = field(default_factory=list)
    groups: Optional[List[GroupTypeSchema]] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> 'SetupConfig':
        actions = []
        for a in d['actions']:
            if a['type'] == 'action':
                actions.append(GroupActionType(**a))
            elif a['type'] == 'command':
                actions.append(CommandActionType(**a))
            elif a['type'] == 'playbook':
                actions.append(PlaybookActionType(**a))
            else:
                raise ValueError(f"Unknown type {a['type']}")
        groups = [GroupTypeSchema(**g) for g in d['groups']]
        return SetupConfig(actions=actions, groups=groups)


@dataclass
class ClusterOptions:
    ssh_to: Optional[str] = None


@dataclass
class NodeConfig:
    type: str
    count: int = field(metadata=dict(validate=Range(min=0)))
    min_count: Optional[int] = field(metadata=dict(validate=Range(min=0)))
    setups: List[str] = field(default_factory=list)


@dataclass
class _ClusterConfig:
    options: Optional[ClusterOptions]
    before_all: Optional[List[str]] = field(default_factory=list)
    before: Optional[List[str]] = field(default_factory=list)
    after_all: Optional[List[str]] = field(default_factory=list)
    after: Optional[List[str]] = field(default_factory=list)
    nodes: Dict[str, NodeConfig] = field(default_factory=dict)


@dataclass
class ClusterConfigFile(m.Schema):
    setups: Optional[Dict[str, SetupConfig]] = field(default_factory=dict)
    clusters: Optional[Dict[str, _ClusterConfig]] = field(default_factory=dict)


@dataclass
class NodeDescriptor:
    type: str
    count: int
    min_count: int
    setups: List[Tuple[str, SetupConfig]]

    def to_dict(self):
        d = asdict(self)
        d['setups'] = [(name, setup.to_dict())for name, setup in self.setups]
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> 'NodeDescriptor':
        setups = [(name, SetupConfig.from_dict(value)) for name, value in d['setups']]
        return NodeDescriptor(type=d['type'], count=d['count'], min_count=d['min_count'],
                              setups=setups)


@dataclass
class ClusterDescriptor:
    options: ClusterOptions
    before_all: List[Tuple[str, SetupConfig]]
    before: List[Tuple[str, SetupConfig]]
    after_all: List[Tuple[str, SetupConfig]]
    after: List[Tuple[str, SetupConfig]]
    nodes: Dict[str, NodeDescriptor]

    def to_dict(self):
        d = asdict(self)
        d['options'] = asdict(self.options) if self.options else {}
        d['before_all'] = [(name, config.to_dict()) for name, config in self.before_all]
        d['before'] = [(name, config.to_dict()) for name, config in self.before]
        d['after_all'] = [(name, config.to_dict()) for name, config in self.after_all]
        d['after'] = [(name, config.to_dict()) for name, config in self.after]
        d['nodes'] = {node_name: desc.to_dict() for node_name, desc in self.nodes.items()}
        return d

    @staticmethod
    def from_dict(d: dict) -> 'ClusterDescriptor':
        options = ClusterOptions(**d['options'])
        before_all = [(name, SetupConfig.from_dict(value)) for name, value in d['before_all']]
        before = [(name, SetupConfig.from_dict(value)) for name, value in d['before']]
        after_all = [(name, SetupConfig.from_dict(value)) for name, value in d['after_all']]
        after = [(name, SetupConfig.from_dict(value)) for name, value in d['after']]
        nodes = {name: NodeDescriptor.from_dict(value) for name, value in d['nodes'].items()}
        return ClusterDescriptor(options=options, before_all=before_all, before=before,
                                 after_all=after_all, after=after, nodes=nodes)


class ClusterConfigReader(object):
    def __init__(self, cluster_files: List[str], extra: Dict[str, str] = None):
        self.cluster_files = cluster_files
        self.clusters = dict()
        self.setups = dict()
        self.cluster_descriptors = dict()
        self.load_files(extra=extra)

    def load_files(self, extra: Dict[str, str] = None):
        setups = dict()
        clusters = dict()
        redefined_clusters, redefined_setups = [], []
        for cfile in self.cluster_files:
            try:
                with open(cfile, mode='r') as f:
                    data = f.read()
                    # Only for setups really loaded??
                    data = Template(data).render(extra or {})
                    data = yaml.load(data, Loader=yaml.FullLoader)
                    data = class_schema(ClusterConfigFile)().load(data)
                    redefined_setups += [key for key in data.setups.keys() if key in setups]
                    redefined_clusters += [key for key in data.clusters.keys() if key in clusters]
                    setups.update(data.setups)
                    clusters.update(data.clusters)

            except Exception as e:
                logger.error(f"{type(e).__name__}: {e}")
                logger.error(f"Dropping file `{cfile}`")
            finally:
                pass

        for s in set(redefined_setups):
            logger.error(f"Setup `{s}` was declared more than once...")
        for c in set(redefined_clusters):
            logger.error(f"Cluster `{c}` was declared more than once...")

        remove_keys = []
        for cluster_name, cluster in clusters.items():
            node_descriptors = {}
            # Check if setups are valid
            try:
                descriptor_before_all = [(setup, setups[setup]) for setup in cluster.before_all]
                descriptor_before = [(setup, setups[setup]) for setup in cluster.before]
                descriptor_after_all = [(setup, setups[setup]) for setup in cluster.after_all]
                descriptor_after = [(setup, setups[setup]) for setup in cluster.after]

                clusters[cluster_name].before_all = [setups[setup] for setup in cluster.before_all]
                clusters[cluster_name].before = [setups[setup] for setup in cluster.before]
                clusters[cluster_name].after_all = [setups[setup] for setup in cluster.after_all]
                clusters[cluster_name].after = [setups[setup] for setup in cluster.after]

                # Check if min_count is less than or equal count
                for node_name, node in cluster.nodes.items():
                    if not node.min_count:
                        cluster.nodes[node_name].min_count = node.count
                    elif node.min_count > node.count:
                        raise Exception(
                            f"Invalid configuration at `{node_name}`: min_count value is higher than count value")

                    node_desc = NodeDescriptor(type=node.type, count=node.count, min_count=node.min_count,
                                               setups=[(setup, setups[setup]) for setup in node.setups])
                    node_descriptors[node_name] = node_desc

                    cluster.nodes[node_name].setups = [setups[setup] for setup in node.setups]
            except Exception as e:
                logger.error(f'Invalid cluster configuration for cluster `{cluster_name}`: {type(e).__name__}: {e}')
                logger.error(f"Dropping cluster configuration `{cluster_name}`")
                remove_keys.append(cluster_name)
                continue

            # Create the descriptor
            descriptor_options = cluster.options
            self.cluster_descriptors[cluster_name] = ClusterDescriptor(
                options=descriptor_options, before_all=descriptor_before_all, before=descriptor_before,
                after_all=descriptor_after_all, after=descriptor_after, nodes=node_descriptors)

        for r in remove_keys:
            clusters.pop(r)

        self.setups = setups
        self.clusters = clusters

    def get_cluster_config(self, cluster_name: str) -> _ClusterConfig:
        try:
            return self.clusters[cluster_name]
        except KeyError:
            pass

        raise InvalidClusterConfiguration(cluster_name)

    def get_setup_config(self, setup_name: str) -> SetupConfig:
        try:
            return self.setups[setup_name]
        except KeyError:
            pass

        raise InvalidSetupConfiguration(setup_name)

    def get_cluster_descriptor(self, cluster_id: str) -> ClusterDescriptor:
        try:
            return self.cluster_descriptors[cluster_id]
        except KeyError:
            pass

        raise InvalidClusterConfiguration(cluster_id)

    def get_all_clusters(self) -> Dict[str, _ClusterConfig]:
        return self.clusters

    def get_all_setups(self) -> Dict[str, SetupConfig]:
        return self.setups

    def get_all_cluster_descriptors(self) -> Dict[str, ClusterDescriptor]:
        return self.cluster_descriptors




if __name__ == '__main__':
#     x = {
#         'setups': {
#             'setup-1' : {
#                 'actions':[
#                     {'type': 'command', 'command': 'ls'},
#                     {'type': 'playbook', 'path': 'xxx'}
#                 ]
#             }
#         },
#         'clusters': {
#             'cluster-1': {
#                 'after': ['setup-1'],
#                 'nodes': {
#                     'node-1': {
#                         'type': 'x',
#                         'count': 10,
#                         'min_count': 1,
#                     }
#                 }
#
#             }
#         }
#     }
#     k = class_schema(ClusterConfigFile)().load(x)
#
#     print(k)

    y = ClusterConfigReader(['/home/lopani/.clap/configs/clusters/cluster-example.yml',
        '/home/lopani/.clap/configs/clusters/cluster-example-2.yml'])
    #y.load_files(extra={'act': 'action'})
    cluster = y.get_cluster_descriptor('cluster-legal')
    print(cluster)

    cluster_dict = cluster.to_dict()
    print(cluster_dict)

    print('')

    cluster = ClusterDescriptor.from_dict(cluster_dict)
    print(cluster)

    cluster_dict_2 = cluster.to_dict()
    print(cluster_dict_2)

    assertDictEqual(cluster_dict, cluster_dict_2)
    assertDictEqual(cluster_dict_2, cluster_dict)
