from typing import Dict, Callable
from SpiffWorkflow.task import Task


ServiceHandler = Callable[[Task], None]
SERVICE_HANDLERS: Dict[str, ServiceHandler] = {}


def service_task(name: str):
    def _decorator(fn: ServiceHandler):
        SERVICE_HANDLERS[name] = fn
        return fn

    return _decorator