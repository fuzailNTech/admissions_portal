"""Workflow engine utilities: run and persist state + step current_tasks."""
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any

from sqlalchemy.orm import Session, joinedload
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow
from SpiffWorkflow.util.task import TaskState

from app.bpm.engine import run_service_tasks, dumps_wf, loads_wf
from app.database.models.workflow import WorkflowInstance, WorkflowInstanceStep


def run_service_tasks_and_persist_steps(
    wf: BpmnWorkflow,
    db: Session,
    wf_row: WorkflowInstance,
    user=None,
    auto_persist: bool = True,
) -> Tuple[bool, List[str], Dict[str, List[str]]]:
    """
    Run service tasks, then persist workflow state and update each step's current_tasks.
    Use this whenever you run the engine and want DB (instance + steps) to stay in sync.

    Returns:
        Same as run_service_tasks: (should_persist, waiting_task_ids, waiting_tasks_by_called_element)
    """
    should_persist, waiting_task_ids, waiting_tasks_by_called_element = run_service_tasks(
        wf, db, wf_row, user, auto_persist
    )
    if should_persist:
        wf_row.state = dumps_wf(wf)
        steps = (
            db.query(WorkflowInstanceStep)
            .options(joinedload(WorkflowInstanceStep.workflow_catalog))
            .filter(WorkflowInstanceStep.workflow_instance_id == wf_row.id)
            .all()
        )
        for step in steps:
            called_element = step.workflow_catalog.process_id
            step.current_tasks = waiting_tasks_by_called_element.get(called_element) or []
        if wf.is_completed():
            wf_row.status = "completed"
            wf_row.completed_at = datetime.utcnow()
    return should_persist, waiting_task_ids, waiting_tasks_by_called_element


def complete_user_task_and_persist(
    wf_row: WorkflowInstance,
    db: Session,
    task_id: str,
    task_data: Optional[Dict[str, Any]] = None,
    user: Optional[Any] = None,
) -> Tuple[bool, bool, List[str], Dict[str, List[str]]]:
    """
    Complete a single user task by task_id, then run service tasks and persist state + steps.

    Returns:
        (task_found_and_completed, should_persist, waiting_task_ids, waiting_tasks_by_called_element)
    """
    wf = loads_wf(wf_row.state)
    waiting = list(wf.get_tasks(state=TaskState.WAITING))
    ready = list(wf.get_tasks(state=TaskState.READY))
    task_found = False
    for t in waiting + ready:
        tid = getattr(t.task_spec, "bpmn_id", None) or getattr(t.task_spec, "name", None)
        if tid == task_id:
            if task_data:
                t.data.update(task_data)
                wf.data.update(task_data)
            t.complete()
            wf.refresh_waiting_tasks()
            task_found = True
            break
    if not task_found:
        return False, False, [], {}
    should_persist, waiting_task_ids, waiting_tasks_by_called_element = run_service_tasks_and_persist_steps(
        wf, db, wf_row, user
    )
    return True, should_persist, waiting_task_ids, waiting_tasks_by_called_element
