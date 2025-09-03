import pickle
from typing import Optional
from SpiffWorkflow.workflow import TaskState
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow
from SpiffWorkflow.bpmn.script_engine import PythonScriptEngine
from SpiffWorkflow.bpmn.parser import BpmnParser
from sqlalchemy.orm import Session
from app.database.models.workflow import WorkflowInstance, User
from app.bpm.handlers import HANDLERS
from datetime import timedelta
from SpiffWorkflow.bpmn.specs.event_definitions.multiple import MultipleEventDefinition
from SpiffWorkflow.bpmn.specs.event_definitions.message import MessageEventDefinition

engine = PythonScriptEngine(environment={"timedelta": timedelta})


def spec_key(ts):
    return getattr(ts, "bpmn_id", None)


def load_spec(path: str, spec_name: str = "user_registration"):
    parser = BpmnParser()
    parser.add_bpmn_file(path)
    spec = parser.get_spec(spec_name)
    return spec


def create_workflow_instance(spec, data: dict | None = None) -> BpmnWorkflow:
    workflow = BpmnWorkflow(spec=spec, script_engine=PythonScriptEngine())
    if data:
        workflow.data.update(data)
    return workflow


def dumps_wf(wf: BpmnWorkflow) -> bytes:
    return pickle.dumps(wf)


def loads_wf(blob: bytes) -> BpmnWorkflow:
    return pickle.loads(blob)


def run_until_waiting(
    wf: BpmnWorkflow, db: Session, wf_row: WorkflowInstance, user: Optional[User] = None
):
    """
    Repeatedly run ready service tasks we know about, then stop when waiting or finished.
    Bind by BPMN element IDs (safer than names).
    """
    while True:
        ready = list(wf.get_tasks(state=TaskState.READY))
        print("Ready tasks:", [t.task_spec.bpmn_id for t in ready])
        if not ready:
            break

        progressed = False
        for t in ready:
            tid = t.task_spec.bpmn_id
            task_handler = HANDLERS.get(tid)

            if task_handler:
                (
                    task_handler(task=t, db=db, wf_row=wf_row, user=user)
                    if user
                    else task_handler(task=t, db=db, wf_row=wf_row)
                )
                t.complete()
                progressed = True
            else:
                # e.g. Start/End events → just complete them
                t.complete()
                progressed = True

        if not progressed:
            break

    # persist after advancing
    wf_row.state = dumps_wf(wf)
    db.flush()


def complete_waiting_task(wf: BpmnWorkflow, bpmn_id: str, data: dict = None):
    waiting = wf.get_tasks(state=TaskState.WAITING)

    for t in waiting:

        if t.task_spec.bpmn_id == bpmn_id:
            t.complete()
            if data:
                wf.data.update(data)
            return


def correlate_message(
    wf: BpmnWorkflow,
    name: str,  # message name
    data: dict = None,
) -> None:
    """
    Deliver a BPMN message to the workflow by completing the matching
    Message Intermediate Catch Event that is WAITING.
    Match by message 'name' (preferred) or by catch event bpmn_id.
    """
    hits = []

    waiting = wf.get_tasks(state=TaskState.WAITING)
    print("Waiting tasks:", [t.task_spec.bpmn_id for t in waiting])

    for t in waiting:
        spec = t.task_spec
        ed = getattr(spec, "event_definition", None)

        # Resolve to a MessageEventDefinition if it's a Multiple
        msg_def = None
        if isinstance(ed, MessageEventDefinition):
            msg_def = ed
        elif isinstance(ed, MultipleEventDefinition):
            # Multiple can wrap several defs; pick the message one if present
            for inner in getattr(ed, "event_definitions", []) or []:
                if isinstance(inner, MessageEventDefinition):
                    msg_def = inner
                    break

        if msg_def is None:
            continue

        msg_name = getattr(msg_def, "name", None)
        spec_id = getattr(spec, "bpmn_id", None)

        print(f"Message wait: id={spec_id} name={msg_name}")

        if name and msg_name == name:
            print("Message correlated by name:", msg_name)
            hits.append(t)

    if not hits:
        raise Exception(409, "Workflow is not waiting for that message.")
    if len(hits) > 1:
        raise Exception(409, "Ambiguous: multiple matching message waits.")

    if data:
        wf.data.update(data)

    hits[0].complete()
