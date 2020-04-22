from typing import Dict, Any

from clap.common.factory import PlatformFactory

def list_templates() -> Dict[str, Any]:
    multi_instance = PlatformFactory.get_instance_api()
    return multi_instance.get_instance_templates()