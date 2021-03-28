import click
import yaml

from typing import List, Dict

from app.module import clap_command
from modules.spits import SpitsModule


@clap_command
@click.group(help='SPITS nodes')
def spits():
    pass


@spits.command('query')
@click.argument('node_id', nargs=-1)
@click.option('-j', '--job', required=True, default=None, type=str, help="Id of the job to query")
@click.option('-p', '--pypits-path', default=None, type=str, help="Optional pypits directory path")
@click.option('-s', '--spits-job-path', default=None, type=str, help="Optional spits-job directory path")
@click.option('-i', '--indent', default=4, show_default=True, nargs=1, type=int, help="Indentation level")
def query(node_id, job, pypits_path, spits_job_path, indent):
    """Query for SPITS job status.

    The optional NODE_ID parameter is the nodes to query.
    """
    if not job:
        raise ValueError(f"Must inform job id")

    node_ids = None if not node_id else list(node_id)
    spits_module = SpitsModule.get_module()
    metrics = spits_module.query_job_status(
        job, node_ids=node_ids, pypits_path=pypits_path, spits_job_path=spits_job_path)
    if metrics:
        print(yaml.dump(metrics, sort_keys=True, indent=indent))
    else:
        print("No metrics")
    return 0
