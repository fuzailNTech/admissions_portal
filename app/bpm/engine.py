import pickle
from typing import Optional, Dict, Any, List, Tuple
from lxml import etree
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow
from SpiffWorkflow.bpmn.parser import BpmnParser
from sqlalchemy.orm import Session
from app.database.models.workflow import WorkflowInstance
from app.database.models.auth import User
from app.bpm.handlers.config import SERVICE_HANDLERS
from SpiffWorkflow.util.task import TaskState


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
    subprocess_registry: Optional[Dict[str, Tuple[str, str]]] = None,
) -> Tuple[Any, Dict[str, Any]]:
    """
    Load BPMN spec from XML string (from DB).

    Args:
        xml_string: BPMN XML as string
        spec_name: Name of the process to load (process ID)
        subprocess_registry: Optional dict mapping calledElement -> (subprocess_xml, subprocess_id)
                            e.g., {"docs.verification_2": ("<xml>...</xml>", "docs.verification_2")}

    Returns:
        Tuple of (BpmnProcessSpec, subprocess_specs_dict)
        The subprocess_specs_dict maps subprocess_id -> BpmnProcessSpec
    """
    parser = BpmnParser()

    # Register subprocesses FIRST (before main process)
    # This ensures they're available when the main process references them
    if subprocess_registry:
        print(f"Registering {len(subprocess_registry)} subprocesses...")
        for called_element, (
            subprocess_xml,
            subprocess_id,
        ) in subprocess_registry.items():
            print(
                f"  Registering subprocess: {called_element} -> process_id: {subprocess_id}"
            )

            # Parse subprocess XML to element tree
            try:
                subprocess_tree = etree.fromstring(subprocess_xml.encode("utf-8"))

                # Add to parser
                parser.add_bpmn_xml(subprocess_tree)

            except etree.XMLSyntaxError as e:
                print(f"  ✗ XML parsing error for subprocess '{subprocess_id}': {e}")
                raise
            except Exception as e:
                print(f"  ✗ Failed to register subprocess '{subprocess_id}': {e}")
                import traceback

                traceback.print_exc()
                raise

    # Parse XML string to element tree
    xml_tree = etree.fromstring(xml_string.encode("utf-8"))

    # Add the main process from XML element tree
    parser.add_bpmn_xml(xml_tree)

    spec = parser.get_spec(spec_name)

    # This ensures they remain accessible to the workflow instance at runtime
    subprocess_specs = {}
    if subprocess_registry:
        print(f"Extracting subprocess specs from parser...")
        for called_element, (
            subprocess_xml,
            subprocess_id,
        ) in subprocess_registry.items():
            try:
                subprocess_specs[called_element] = parser.get_spec(subprocess_id)
                print(
                    f"  ✓ Extracted subprocess spec '{subprocess_id}' with key '{called_element}'"
                )
            except Exception as e:
                print(f"  ✗ Could not extract subprocess spec '{subprocess_id}': {e}")

    return spec, subprocess_specs


def create_workflow_instance(
    spec, subprocess_specs: Dict[str, Any] = None, data: dict | None = None
) -> BpmnWorkflow:
    """Create a new workflow instance from a spec with subprocess specs.

    Args:
        spec: The main BpmnProcessSpec
        subprocess_specs: Dict mapping calledElement -> BpmnProcessSpec for subprocesses
        data: Initial workflow data

    Returns:
        BpmnWorkflow instance
    """
    # Debug: Check spec structure before creating workflow
    print(f"Creating workflow instance from spec: {type(spec)}")
    if subprocess_specs:
        try:
            print(
                f"  With {len(subprocess_specs)} subprocess specs: {list(subprocess_specs.keys())}"
            )
            workflow = BpmnWorkflow(spec=spec, subprocess_specs=subprocess_specs)
        except TypeError as e:
            print(f"  ✗ BpmnWorkflow doesn't accept subprocess_specs parameter: {e}")
            raise
    else:
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


def filter_exclusive_gateway_tasks(wf: BpmnWorkflow, gateway_task, ready_tasks: List) -> None:
    """
    Workaround for SpiffWorkflow bug where exclusive gateways activate multiple paths.
    
    SpiffWorkflow sometimes incorrectly makes multiple tasks READY after an exclusive gateway,
    when only one path should be taken. This function manually evaluates conditions and cancels
    tasks from non-taken paths to ensure correct exclusive gateway behavior.
    
    Args:
        wf: The workflow instance
        gateway_task: The completed gateway task
        ready_tasks: List of tasks that became READY after the gateway
    """
    if len(ready_tasks) <= 1:
        # Only one path taken - this is correct behavior
        return
    
    # Multiple tasks are READY - need to filter (SpiffWorkflow bug workaround)
    print(f"  WARNING: Exclusive gateway produced {len(ready_tasks)} READY tasks - filtering manually")
    
    gateway_spec = gateway_task.task_spec
    task_conditions = {}
    default_task_spec = None
    
    # Get default task spec
    if hasattr(gateway_spec, 'default_task_spec'):
        default_task_spec = gateway_spec.default_task_spec
    
    # Get conditional task specs and extract conditions
    if hasattr(gateway_spec, 'cond_task_specs') and gateway_spec.cond_task_specs:
        for cond, task_name in gateway_spec.cond_task_specs:
            if cond is not None:
                # Extract condition expression from _BpmnCondition object
                condition_expr = None
                if hasattr(cond, 'args') and cond.args:
                    condition_expr = cond.args[0] if isinstance(cond.args, (list, tuple)) else cond.args
                elif hasattr(cond, 'condition'):
                    condition_expr = cond.condition
                else:
                    condition_expr = cond
                
                task_conditions[task_name] = condition_expr
    
    # Get default task ID for comparison
    default_id = None
    if default_task_spec:
        default_id = default_task_spec.bpmn_id if hasattr(default_task_spec, 'bpmn_id') else (
            default_task_spec.name if hasattr(default_task_spec, 'name') else str(default_task_spec)
        )
    
    # PASS 1: Evaluate all conditions to determine if any matched
    task_results = {}
    condition_matched = False
    
    for task in ready_tasks:
        task_spec = task.task_spec
        task_id = task_spec.bpmn_id if hasattr(task_spec, 'bpmn_id') else task_spec.name
        is_default = default_id and (task_spec == default_task_spec or task_id == default_id)
        condition_result = None
        
        if task_id in task_conditions:
            condition = task_conditions[task_id]
            try:
                # Evaluate condition (callable or expression)
                if hasattr(condition, '__call__'):
                    result = condition(task)
                else:
                    result = wf.script_engine.evaluate(gateway_task, condition)
                
                condition_result = result
                if result:
                    condition_matched = True
                    print(f"    Condition matched for {task_id}")
            except Exception as e:
                print(f"    Failed to evaluate condition for {task_id}: {e}")
                condition_result = False
        
        task_results[task_id] = (task, is_default, condition_result)
    
    # PASS 2: Decide which tasks to keep
    tasks_to_keep = []
    tasks_to_cancel = []
    
    for task_id, (task, is_default, condition_result) in task_results.items():
        if condition_result is True:
            tasks_to_keep.append(task)
        elif is_default and not condition_matched:
            tasks_to_keep.append(task)
        else:
            tasks_to_cancel.append(task)
    
    # Fallback: if we couldn't determine which to keep, keep only the first one
    if not tasks_to_keep:
        print(f"  WARNING: Could not determine correct path - keeping first task")
        tasks_to_keep = [ready_tasks[0]]
        tasks_to_cancel = ready_tasks[1:]
    
    # Cancel tasks from non-taken paths
    for task in tasks_to_cancel:
        task.cancel()
    
    kept_task_ids = [t.task_spec.bpmn_id for t in tasks_to_keep]
    print(f"  Filtered gateway paths: keeping {kept_task_ids}")


def get_task_type(task) -> str:
    """
    Determine task type: 'service', 'user', 'callActivity', or 'other'.

    Returns:
        Task type string
    """
    spec = task.task_spec

    # Check if it's a user task (manual task)
    if hasattr(spec, "manual") and spec.manual:
        return "user"

    # Check if it's a callActivity (subprocess)
    if hasattr(spec, "called_element") or hasattr(spec, "spec"):
        return "callActivity"

    # Check if it's a service task (has handler or is service task)
    if hasattr(spec, "bpmn_id") and spec.bpmn_id in SERVICE_HANDLERS:
        return "service"

    # Check for other BPMN task types
    if hasattr(spec, "__class__"):
        class_name = spec.__class__.__name__.lower()
        if "service" in class_name:
            return "service"
        if "user" in class_name or "manual" in class_name:
            return "user"

    return "other"


def run_service_tasks(
    wf: BpmnWorkflow,
    db: Session,
    wf_row: WorkflowInstance,
    user: Optional[User] = None,
    auto_persist: bool = True,
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
            user_tasks = [t for t in waiting if get_task_type(t) == "user"]
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
        spec_name = t.task_spec.bpmn_id if hasattr(t.task_spec, "bpmn_id") else None

        print(f"Processing {task_type} task: {spec_name}")

        try:
            if task_type == "user":
                # User task - stop execution and persist
                print(f"User task encountered: {spec_name} - stopping execution")
                waiting_task_ids.append(spec_name)
                return True, waiting_task_ids

            elif task_type == "callActivity":
                # Subprocess call - let SpiffWorkflow handle it
                print(f"Executing callActivity: {spec_name}")
                # Debug: Check callActivity task spec
                if hasattr(t.task_spec, "called_element"):
                    print(f"  Called element: {t.task_spec.called_element}")
                if hasattr(t.task_spec, "spec"):
                    print(f"  Task spec has subprocess spec: {t.task_spec.spec}")
                # Try to complete the task - this will trigger subprocess resolution
                try:
                    t.complete()
                    print(f"Completed callActivity: {spec_name}")
                except Exception as e:
                    print(f"Error completing callActivity {spec_name}: {e}")
                    print(f"  Error type: {type(e)}")
                    import traceback

                    traceback.print_exc()
                    raise

            elif task_type == "service":
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

                is_gateway = spec_name and (
                    "gateway" in spec_name.lower() or "gw" in spec_name.lower()
                )

                t.complete()

                # WORKAROUND: SpiffWorkflow sometimes activates multiple paths from exclusive gateways
                # Filter out incorrectly activated tasks after gateway completion
                if is_gateway:
                    wf.refresh_waiting_tasks()
                    ready_tasks = [task for task in wf.get_tasks(state=TaskState.READY)]
                    filter_exclusive_gateway_tasks(wf, t, ready_tasks)

            made_progress = True

            # Check if workflow completed after this task
            if wf.is_completed():
                print(f"Workflow completed after task: {spec_name}")
                return True, []

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
    wf: BpmnWorkflow, wf_row: WorkflowInstance, db: Session
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
    task_data: Optional[Dict[str, Any]] = None,
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


# from SpiffWorkflow.bpmn.specs.event_definitions.multiple import MultipleEventDefinition
# from SpiffWorkflow.bpmn.specs.event_definitions.message import MessageEventDefinition
# def correlate_message(
#     wf: BpmnWorkflow, message_name: str, payload: dict | None = None
# ) -> bool:
#     """
#     Complete the matching Message Intermediate Catch Event waiting for `message_name`.
#     Returns True if a task was found and completed.
#     """
#     # Find WAITING tasks whose spec has a message name equal to message_name
#     waiting = wf.get_tasks(state=TaskState.WAITING)
#     print("Correlate waiting tasks:", [t.task_spec.bpmn_id for t in waiting])
#     for t in waiting:
#         spec: TaskSpec = t.task_spec
#         ed = getattr(spec, "event_definition", None)

#         msg_def = None
#         if isinstance(ed, MessageEventDefinition):
#             msg_def = ed
#         elif isinstance(ed, MultipleEventDefinition):
#             for inner in getattr(ed, "event_definitions", []) or []:
#                 if isinstance(inner, MessageEventDefinition):
#                     msg_def = inner
#                     break

#         if msg_def is None:
#             continue

#         msg_name = getattr(msg_def, "name", None)

#         print(f"Task {spec.bpmn_id} has message name: {msg_name}")
#         if msg_name == message_name:
#             if payload:
#                 wf.data.update(payload)
#                 t.data.update(payload)
#             t.complete()
#             wf.refresh_waiting_tasks()
#             completed = [t for t in wf.get_tasks(state=TaskState.COMPLETED)]
#             print("completed tasks:", [f"{t.task_spec.bpmn_id}({t.state})" for t in completed])
#             return True
#     return False
