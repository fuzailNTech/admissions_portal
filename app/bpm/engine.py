import pickle
import io
from typing import Optional, Dict, Any, List, Tuple
from lxml import etree
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow
from SpiffWorkflow.bpmn.parser import BpmnParser
from sqlalchemy.orm import Session
from app.database.models.workflow import WorkflowInstance
from app.database.models.auth import User
from app.bpm.handlers.auth import SERVICE_HANDLERS
from SpiffWorkflow.specs.base import TaskSpec
from SpiffWorkflow.util.task import TaskState
from SpiffWorkflow.bpmn.specs.event_definitions.multiple import MultipleEventDefinition
from SpiffWorkflow.bpmn.specs.event_definitions.message import MessageEventDefinition


def spec_key(ts):
    return getattr(ts, "bpmn_id", None)


def load_spec(path: str, spec_name: str = "user_registration"):
    """Load BPMN spec from a file path (legacy support)."""
    parser = BpmnParser()
    parser.add_bpmn_file(path)
    spec = parser.get_spec(spec_name)
    return spec


def load_spec_from_xml(
    xml_string: str, 
    spec_name: str,
    subprocess_registry: Optional[Dict[str, Tuple[str, str]]] = None
):
    """
    Load BPMN spec from XML string (from DB).
    
    Args:
        xml_string: BPMN XML as string
        spec_name: Name of the process to load (process ID)
        subprocess_registry: Optional dict mapping calledElement -> (subprocess_xml, subprocess_id)
                            e.g., {"docs.verification@v2": ("<xml>...</xml>", "docs_verification_v2")}
    
    Returns:
        BpmnProcessSpec
    """
    parser = BpmnParser()
    
    # Parse XML string to element tree
    xml_tree = etree.fromstring(xml_string.encode('utf-8'))
    
    # Add the main process from XML element tree
    parser.add_bpmn_xml(xml_tree)
    
    # Register subprocesses if provided (for callActivity support)
    if subprocess_registry:
        for called_element, (subprocess_xml, subprocess_id) in subprocess_registry.items():
            # Parse subprocess XML to element tree
            subprocess_tree = etree.fromstring(subprocess_xml.encode('utf-8'))
            parser.add_bpmn_xml(subprocess_tree)
            # SpiffWorkflow will match calledElement to process ID automatically
    
    spec = parser.get_spec(spec_name)
    return spec


def create_workflow_instance(spec, data: dict | None = None) -> BpmnWorkflow:
    """Create a new workflow instance from a spec."""
    workflow = BpmnWorkflow(spec=spec)
    if data:
        workflow.data.update(data)
    return workflow


def dumps_wf(wf: BpmnWorkflow) -> bytes:
    """Serialize workflow state to bytes for DB storage."""
    return pickle.dumps(wf)

 
def loads_wf(blob: bytes) -> BpmnWorkflow:
    """Deserialize workflow state from DB."""
    return pickle.loads(blob)


def get_task_type(task) -> str:
    """
    Determine task type: 'service', 'user', 'callActivity', or 'other'.
    
    Returns:
        Task type string
    """
    spec = task.task_spec
    
    # Check if it's a user task (manual task)
    if hasattr(spec, 'manual') and spec.manual:
        return 'user'
    
    # Check if it's a callActivity (subprocess)
    if hasattr(spec, 'called_element') or hasattr(spec, 'spec'):
        return 'callActivity'
    
    # Check if it's a service task (has handler or is service task)
    if hasattr(spec, 'bpmn_id') and spec.bpmn_id in SERVICE_HANDLERS:
        return 'service'
    
    # Check for other BPMN task types
    if hasattr(spec, '__class__'):
        class_name = spec.__class__.__name__.lower()
        if 'service' in class_name:
            return 'service'
        if 'user' in class_name or 'manual' in class_name:
            return 'user'
    
    return 'other'


def run_service_tasks(
    wf: BpmnWorkflow, 
    db: Session, 
    wf_row: WorkflowInstance, 
    user: Optional[User] = None,
    auto_persist: bool = True
) -> Tuple[bool, List[str]]:
    """
    Execute service tasks until hitting a user task or waiting event.
    
    Args:
        wf: The workflow instance
        db: Database session
        wf_row: WorkflowInstance row for persistence
        user: Optional user context
        auto_persist: If True, automatically persist state after each batch
    
    Returns:
        Tuple of (should_persist, waiting_task_ids)
        - should_persist: True if workflow hit a user task or waiting event
        - waiting_task_ids: List of task IDs that are waiting (user tasks or events)
    """
    # 1) Consume StartEvent and any automatic work
    wf.refresh_waiting_tasks()

    made_progress = True
    waiting_task_ids = []
    
    while made_progress:
        made_progress = False

        # 2) Fetch the next READY task
        t = wf.get_next_task(state=TaskState.READY)
        
        if t is None:
            # No more READY tasks, check for waiting tasks
            wf.refresh_waiting_tasks()
            waiting = [t for t in wf.get_tasks(state=TaskState.WAITING)]
            waiting_task_ids = [t.task_spec.bpmn_id for t in waiting]
            
            # Check if any are user tasks
            user_tasks = [t for t in waiting if get_task_type(t) == 'user']
            if user_tasks:
                print(f"Hit user tasks: {[t.task_spec.bpmn_id for t in user_tasks]}")
                return True, waiting_task_ids
            
            # Check if workflow is completed
            if wf.is_completed():
                print("Workflow completed")
                return True, []
            
            # Otherwise, we're waiting on events/timers
            print(f"Waiting on events/timers: {waiting_task_ids}")
            return True, waiting_task_ids

        task_type = get_task_type(t)
        spec_name = t.task_spec.bpmn_id
        
        print(f"Processing {task_type} task: {spec_name}")

        try:
            if task_type == 'user':
                # User task - stop execution and persist
                print(f"User task encountered: {spec_name} - stopping execution")
                waiting_task_ids.append(spec_name)
                return True, waiting_task_ids
            
            elif task_type == 'callActivity':
                # Subprocess call - let SpiffWorkflow handle it
                print(f"Executing callActivity: {spec_name}")
                t.complete()
                print(f"Completed callActivity: {spec_name}")
            
            elif task_type == 'service':
                # Service task - use handler
                handler = SERVICE_HANDLERS.get(spec_name)
                if handler:
                    print(f"Executing service handler for: {spec_name}")
                    if user:
                        handler(task=t, db=db, wf_row=wf_row, user=user)
                    else:
                        handler(task=t, db=db, wf_row=wf_row)
                    t.complete()
                    print(f"Completed service task: {spec_name}")
                else:
                    # Service task without handler - complete anyway
                    print(f"Service task {spec_name} has no handler - completing")
                    t.complete()
            
            else:
                # Other task types (gateways, events, etc.) - let engine handle
                print(f"Executing engine task: {spec_name}")
                t.complete()
            
            made_progress = True

            # 3) Promote graph after each completion
            wf.refresh_waiting_tasks()

        except Exception as e:
            print(f"Error in task {spec_name}: {e}")
            raise

    # Final refresh
    wf.refresh_waiting_tasks()
    
    # Check final state
    waiting = [t for t in wf.get_tasks(state=TaskState.WAITING)]
    waiting_task_ids = [t.task_spec.bpmn_id for t in waiting]
    
    # Show current state
    print("waiting tasks:", [f"{t.task_spec.bpmn_id}({t.state})" for t in waiting])
    completed = [t for t in wf.get_tasks(state=TaskState.COMPLETED)]
    print("completed tasks:", [f"{t.task_spec.bpmn_id}({t.state})" for t in completed])
    
    # Persist if we hit waiting tasks or completed
    should_persist = len(waiting_task_ids) > 0 or wf.is_completed()
    
    if should_persist and auto_persist:
        wf_row.state = dumps_wf(wf)
        db.add(wf_row)
        db.flush()
    
    return should_persist, waiting_task_ids


def persist_workflow_state(
    wf: BpmnWorkflow,
    wf_row: WorkflowInstance,
    db: Session
) -> None:
    """
    Explicitly persist workflow state to DB.
    Call this after run_service_tasks() or when resuming workflow.
    """
    wf_row.state = dumps_wf(wf)
    db.add(wf_row)
    db.flush()


def resume_workflow(
    wf_row: WorkflowInstance,
    db: Session,
    user: Optional[User] = None,
    task_id: Optional[str] = None,
    task_data: Optional[Dict[str, Any]] = None
) -> Tuple[bool, List[str]]:
    """
    Resume a workflow from a persisted state.
    
    Args:
        wf_row: WorkflowInstance row from DB
        db: Database session
        user: Optional user context
        task_id: Optional task ID to complete (for user tasks)
        task_data: Optional data to inject when completing task
    
    Returns:
        Tuple of (should_persist, waiting_task_ids)
    """
    # Load workflow from DB
    wf = loads_wf(wf_row.state)
    
    # If completing a specific task (e.g., user task)
    if task_id:
        tasks = wf.get_tasks(state=TaskState.WAITING)
        for t in tasks:
            if t.task_spec.bpmn_id == task_id:
                if task_data:
                    t.data.update(task_data)
                    wf.data.update(task_data)
                t.complete()
                wf.refresh_waiting_tasks()
                break
    
    # Continue execution
    return run_service_tasks(wf, db, wf_row, user)


def correlate_message(
    wf: BpmnWorkflow, message_name: str, payload: dict | None = None
) -> bool:
    """
    Complete the matching Message Intermediate Catch Event waiting for `message_name`.
    Returns True if a task was found and completed.
    """
    # Find WAITING tasks whose spec has a message name equal to message_name
    waiting = wf.get_tasks(state=TaskState.WAITING)
    print("Correlate waiting tasks:", [t.task_spec.bpmn_id for t in waiting])
    for t in waiting:
        spec: TaskSpec = t.task_spec
        ed = getattr(spec, "event_definition", None)

        msg_def = None
        if isinstance(ed, MessageEventDefinition):
            msg_def = ed
        elif isinstance(ed, MultipleEventDefinition):
            for inner in getattr(ed, "event_definitions", []) or []:
                if isinstance(inner, MessageEventDefinition):
                    msg_def = inner
                    break

        if msg_def is None:
            continue

        msg_name = getattr(msg_def, "name", None)

        print(f"Task {spec.bpmn_id} has message name: {msg_name}")
        if msg_name == message_name:
            if payload:
                wf.data.update(payload)
                t.data.update(payload)
            t.complete()
            wf.refresh_waiting_tasks()
            completed = [t for t in wf.get_tasks(state=TaskState.COMPLETED)]
            print("completed tasks:", [f"{t.task_spec.bpmn_id}({t.state})" for t in completed])
            return True
    return False
