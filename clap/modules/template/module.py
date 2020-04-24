from typing import Dict, Any, List

from clap.common.factory import PlatformFactory

def list_templates() -> Dict[str, Any]:
    multi_instance = PlatformFactory.get_instance_api()
    return multi_instance.get_instance_templates()

def list_instance_types() -> List[str]:
    multi_instance = PlatformFactory.get_instance_api()
    return list(multi_instance.get_instance_templates().keys())