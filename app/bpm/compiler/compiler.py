"""
Phase-1 BPMN Compiler (Manifest → BPMN XML)

Simplified: handles start, call, exclusive gateway, and end nodes.
"""

import os
from lxml import etree
import json
from typing import Dict, Any, List, Callable, Tuple, Set

# Namespaces
BPMN = "http://www.omg.org/spec/BPMN/20100524/MODEL"
APP = "urn:appfolio:ext"  # custom namespace for your app
NS = {"bpmn": BPMN, "app": APP}

b = lambda tag: f"{{{BPMN}}}{tag}"
a = lambda tag: f"{{{APP}}}{tag}"


# -----------------------------------------------------------
# Validation Helpers
# -----------------------------------------------------------


def validate_manifest(manifest: Dict[str, Any]) -> None:
    """Validate manifest structure and references."""
    if "start" not in manifest:
        raise ValueError("Manifest must define 'start'")
    if "nodes" not in manifest:
        raise ValueError("Manifest missing 'nodes' list")

    # Build node ID set
    node_ids = {n["id"] for n in manifest["nodes"]}

    # Validate start node exists
    if manifest["start"] not in node_ids:
        raise ValueError(f"Start node '{manifest['start']}' not found in nodes")

    # Validate all 'next' references
    for n in manifest["nodes"]:
        if n.get("next") and n["next"] not in node_ids:
            raise ValueError(
                f"Node '{n['id']}' references non-existent next node '{n['next']}'"
            )

    # Validate gateway branches
    for n in manifest["nodes"]:
        if n["type"] == "gateway":
            if "branches" not in n or not n["branches"]:
                raise ValueError(f"Gateway '{n['id']}' must have at least one branch")

            default_count = sum(
                1 for br in n["branches"] if br.get("else") or not br.get("when")
            )
            if default_count != 1:
                raise ValueError(
                    f"Gateway '{n['id']}' must have exactly one default branch (else or no condition)"
                )

            for br in n["branches"]:
                if "to" not in br:
                    raise ValueError(f"Gateway '{n['id']}' branch missing 'to' target")
                if br["to"] not in node_ids:
                    raise ValueError(
                        f"Gateway '{n['id']}' branch references non-existent node '{br['to']}'"
                    )

    # Check for cycles (simple DFS)
    visited: Set[str] = set()
    rec_stack: Set[str] = set()

    def has_cycle(node_id: str) -> bool:
        if node_id in rec_stack:
            return True
        if node_id in visited:
            return False

        visited.add(node_id)
        rec_stack.add(node_id)

        node = next((n for n in manifest["nodes"] if n["id"] == node_id), None)
        if node and node.get("next"):
            if has_cycle(node["next"]):
                return True

        rec_stack.remove(node_id)
        return False

    if has_cycle(manifest["start"]):
        raise ValueError("Manifest contains a cycle in node references")


# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------


def create_doc(process_id: str = "Parent") -> Tuple[etree._ElementTree, etree._Element]:
    defs = etree.Element(b("definitions"), nsmap=NS)
    process = etree.SubElement(defs, b("process"), id=process_id, isExecutable="true")
    return etree.ElementTree(defs), process


def add_start(proc: etree._Element) -> etree._Element:
    return etree.SubElement(proc, b("startEvent"), id="StartEvent_1")


def add_end(proc: etree._Element, node_id: str) -> etree._Element:
    return etree.SubElement(proc, b("endEvent"), id=f"EndEvent__{node_id}")


def add_call(proc: etree._Element, node: Dict[str, Any]) -> etree._Element:
    """Create a callActivity for a subprocess with optional data mapping."""
    called_el = f"{node['subflow_key']}@v{node['subflow_version']}"
    call = etree.SubElement(
        proc,
        b("callActivity"),
        id=node["id"],
        name=node.get("name", node["id"]),
        calledElement=called_el,
    )

    # Add extensionElements for policy reference
    if node.get("policy_ref"):
        ext = etree.SubElement(call, b("extensionElements"))
        etree.SubElement(ext, a("policyRef")).text = node["policy_ref"]

    # Add data input/output mappings if provided
    input_mapping = node.get("input_mapping")
    output_mapping = node.get("output_mapping")

    if input_mapping or output_mapping:
        io_spec = etree.SubElement(call, b("ioSpecification"))

        if input_mapping:
            for var_name, source_expr in input_mapping.items():
                data_input = etree.SubElement(
                    io_spec,
                    b("dataInput"),
                    id=f"{node['id']}_input_{var_name}",
                    name=var_name,
                )
                input_set = etree.SubElement(io_spec, b("inputSet"))
                etree.SubElement(input_set, b("dataInputRefs")).text = data_input.get(
                    "id"
                )

                # Create data input association
                data_input_assoc = etree.SubElement(call, b("dataInputAssociation"))
                source = etree.SubElement(data_input_assoc, b("sourceRef"))
                source.text = source_expr  # Expression or variable reference
                target = etree.SubElement(data_input_assoc, b("targetRef"))
                target.text = data_input.get("id")

        if output_mapping:
            for var_name, target_expr in output_mapping.items():
                data_output = etree.SubElement(
                    io_spec,
                    b("dataOutput"),
                    id=f"{node['id']}_output_{var_name}",
                    name=var_name,
                )
                output_set = etree.SubElement(io_spec, b("outputSet"))
                etree.SubElement(output_set, b("dataOutputRefs")).text = (
                    data_output.get("id")
                )

                # Create data output association
                data_output_assoc = etree.SubElement(call, b("dataOutputAssociation"))
                source = etree.SubElement(data_output_assoc, b("sourceRef"))
                source.text = data_output.get("id")
                target = etree.SubElement(data_output_assoc, b("targetRef"))
                target.text = target_expr  # Expression or variable reference

    return call


def add_gateway(proc: etree._Element, node: Dict[str, Any]) -> etree._Element:
    return etree.SubElement(proc, b("exclusiveGateway"), id=node["id"])


def add_seq(proc: etree._Element, src, tgt, fid, condition=None, is_default=False):
    flow = etree.SubElement(
        proc,
        b("sequenceFlow"),
        id=fid,
        sourceRef=src.get("id"),
        targetRef=tgt.get("id"),
    )
    if condition:
        cond = etree.SubElement(flow, b("conditionExpression"))
        cond.set("{http://www.w3.org/2001/XMLSchema-instance}type", "tFormalExpression")
        cond.text = condition
    if is_default:
        src.set("default", fid)
    return flow


def tostring(tree):
    return etree.tostring(
        tree, pretty_print=True, xml_declaration=True, encoding="UTF-8"
    ).decode()


# -----------------------------------------------------------
# Core Compiler
# -----------------------------------------------------------


def compile_manifest_to_bpmn(
    manifest: Dict[str, Any],
    catalog_lookup: Callable[[str, int], Dict[str, Any]] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Convert manifest JSON → BPMN XML
    Returns (xml_string, subflow_refs)
    """
    # Validate manifest structure and references
    validate_manifest(manifest)

    # Get process ID from manifest or use default
    process_id = manifest.get("process_id", manifest.get("workflow_name", "Parent"))
    # Sanitize process ID (BPMN IDs should be valid XML identifiers)
    process_id = process_id.replace(" ", "_").replace("-", "_")

    tree, proc = create_doc(process_id)
    nodes_xml = {}
    refs = []

    # Build BPMN elements for each node
    for n in manifest["nodes"]:
        if n["type"] == "call":
            if catalog_lookup:
                catalog_lookup(
                    n["subflow_key"], int(n["subflow_version"])
                )  # sanity check
            el = add_call(proc, n)
            refs.append(
                {
                    "subflow_key": n["subflow_key"],
                    "version": int(n["subflow_version"]),
                    "calledElement": f"{n['subflow_key']}@v{n['subflow_version']}",
                }
            )
            nodes_xml[n["id"]] = el

        elif n["type"] == "gateway":
            nodes_xml[n["id"]] = add_gateway(proc, n)

        elif n["type"] == "end":
            nodes_xml[n["id"]] = add_end(proc, n["id"])

    # Add startEvent → start node
    start = add_start(proc)
    start_target = nodes_xml[manifest["start"]]
    add_seq(proc, start, start_target, "Flow__Start")

    # Wire simple next relationships
    flow_idx = 1
    for n in manifest["nodes"]:
        if n["type"] == "call" and n.get("next"):
            src = nodes_xml[n["id"]]
            tgt = nodes_xml[n["next"]]
            add_seq(proc, src, tgt, f"Flow__{flow_idx}")
            flow_idx += 1

    # Wire call nodes without next to end events
    for n in manifest["nodes"]:
        if n["type"] == "call" and not n.get("next"):
            end_el = add_end(proc, n["id"])
            add_seq(proc, nodes_xml[n["id"]], end_el, f"Flow__End__{n['id']}")

    # Wire gateways - fixed to handle "else" branches properly
    for n in manifest["nodes"]:
        if n["type"] == "gateway":
            gw_el = nodes_xml[n["id"]]
            default_flow_id = None

            # First pass: identify default branch
            for br in n["branches"]:
                if br.get("else") or not br.get("when"):
                    default_flow_id = f"Flow__{flow_idx}"
                    break

            # Second pass: create all flows
            for br in n["branches"]:
                tgt = nodes_xml[br["to"]]
                flow_id = f"Flow__{flow_idx}"

                # Check if this is a conditional branch
                if "when" in br and br["when"]:
                    add_seq(proc, gw_el, tgt, flow_id, condition=br["when"])
                else:
                    # This is the default/else branch
                    add_seq(proc, gw_el, tgt, flow_id, is_default=True)

                flow_idx += 1

    return tostring(tree), refs


# -----------------------------------------------------------
# Example usage
# -----------------------------------------------------------
if __name__ == "__main__":
    # Simple registry
    CATALOG = {
        # Communication-related subprocesses
        ("communication.send_email", 1): {
            "process_id": "communication.send_email@v1",
            "checksum": "sha256:email-v1",
            "description": "Sends 'Application Received' email to applicant.",
        },
        ("communication.send_offer", 1): {
            "process_id": "communication.send_offer@v1",
            "checksum": "sha256:offer-v1",
            "description": "Sends admission offer email to applicant.",
        },
        # Application assignment
        ("assign.application", 1): {
            "process_id": "assign.application@v1",
            "checksum": "sha256:assign-v1",
            "description": "Assigns application to admission officer based on policy.",
        },
        # Document verification
        ("docs.verification", 2): {
            "process_id": "docs.verification@v2",
            "checksum": "sha256:verify-v2",
            "description": "Verifies applicant documents against college requirements.",
        },
        ("docs.request_missing", 1): {
            "process_id": "docs.request_missing@v1",
            "checksum": "sha256:reqdocs-v1",
            "description": "Requests missing or incorrect documents from applicant.",
        },
        # Interview
        ("admissions.interview", 3): {
            "process_id": "admissions.interview@v3",
            "checksum": "sha256:interview-v3",
            "description": "Conducts interview and records applicant performance.",
        },
        # Financial evaluation
        ("finance.fee_calculation", 1): {
            "process_id": "finance.fee_calculation@v1",
            "checksum": "sha256:fee-v1",
            "description": "Calculates tuition fee or scholarship based on marks/policies.",
        },
        # Final stages
        ("end.success", 1): {
            "process_id": "end.success@v1",
            "checksum": "sha256:end-success-v1",
            "description": "Marks admission as successful and issues enrollment confirmation.",
        },
        ("end.rejected", 1): {
            "process_id": "end.rejected@v1",
            "checksum": "sha256:end-rejected-v1",
            "description": "Marks application as rejected and notifies the applicant.",
        },
        ("end.cancelled", 1): {
            "process_id": "end.cancelled@v1",
            "checksum": "sha256:end-cancelled-v1",
            "description": "Handles withdrawal or cancellation of admission by applicant.",
        },
    }

    def catalog_lookup(key, ver):
        if (key, ver) not in CATALOG:
            raise ValueError(f"{key}@v{ver} not in catalog")
        return CATALOG[(key, ver)]

    base_dir = os.path.dirname(os.path.abspath(__file__))

    manifest = open(
        f"{base_dir}/example-manifest.json",
    ).read()

    xml, refs = compile_manifest_to_bpmn(json.loads(manifest), catalog_lookup)
    print(xml)
    print("\nRefs:", json.dumps(refs, indent=2))
