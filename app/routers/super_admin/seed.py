from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict
import os
import re
import xml.etree.ElementTree as ET

from app.database.config.db import get_db
from app.database.models.workflow import WorkflowCatalog
from app.database.models.auth import User
from app.utils.auth import require_super_admin
from app.settings import BPMN_DIR

seed_router = APIRouter(
    prefix="/seed",
    tags=["Super Admin - Seed Data"],
)


def extract_process_id_from_bpmn(xml_content: str) -> str:
    """Extract the process ID from BPMN XML."""
    try:
        # Parse XML
        root = ET.fromstring(xml_content)
        
        # Define namespaces
        namespaces = {'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL'}
        
        # Find the process element
        process = root.find('.//bpmn:process', namespaces)
        
        if process is not None:
            process_id = process.get('id')
            if process_id:
                return process_id
        
        raise ValueError("Could not find process ID in BPMN XML")
    except Exception as e:
        raise ValueError(f"Error parsing BPMN XML: {str(e)}")


def extract_subflow_key_from_process_id(process_id: str) -> str:
    """
    Extract subflow_key from process_id.
    
    Example: "operation.admission_decision_v1" -> "operation.admission_decision"
    """
    # Remove version suffix (_v1, _v2, etc.)
    pattern = r'_v\d+$'
    subflow_key = re.sub(pattern, '', process_id)
    return subflow_key


def extract_version_from_process_id(process_id: str) -> int:
    """
    Extract version number from process_id.
    
    Example: "operation.admission_decision_v1" -> 1
    """
    match = re.search(r'_v(\d+)$', process_id)
    if match:
        return int(match.group(1))
    return 1  # Default version


@seed_router.post("/workflow-catalog")
def seed_workflow_catalog(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Seed WorkflowCatalog with BPMN files from bpm/workflows directory.
    
    Requires super admin role.
    Reads all .bpmn files and creates catalog entries.
    Skips files that already exist in the catalog.
    """
    if not os.path.exists(BPMN_DIR):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BPMN directory not found: {BPMN_DIR}",
        )
    
    # Get all BPMN files
    bpmn_files = [f for f in os.listdir(BPMN_DIR) if f.endswith('.bpmn')]
    
    if not bpmn_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No BPMN files found in {BPMN_DIR}",
        )
    
    results = {
        "created": [],
        "skipped": [],
        "errors": [],
    }
    
    for filename in bpmn_files:
        try:
            filepath = os.path.join(BPMN_DIR, filename)
            
            # Read BPMN file
            with open(filepath, 'r', encoding='utf-8') as f:
                bpmn_xml = f.read()
            
            # Extract process information
            process_id = extract_process_id_from_bpmn(bpmn_xml)
            subflow_key = extract_subflow_key_from_process_id(process_id)
            version = extract_version_from_process_id(process_id)
            
            # Check if already exists
            existing = db.query(WorkflowCatalog).filter(
                WorkflowCatalog.subflow_key == subflow_key,
                WorkflowCatalog.version == version
            ).first()
            
            if existing:
                results["skipped"].append({
                    "filename": filename,
                    "subflow_key": subflow_key,
                    "version": version,
                    "reason": "Already exists in catalog"
                })
                continue
            
            # Create workflow catalog entry
            workflow_catalog = WorkflowCatalog(
                subflow_key=subflow_key,
                version=version,
                process_id=process_id,
                bpmn_xml=bpmn_xml,
                description=f"Workflow: {filename.replace('.bpmn', '').replace('_', ' ').title()}",
                published=True,  # Auto-publish seeded workflows
                created_by=current_user.id,
            )
            
            db.add(workflow_catalog)
            db.commit()
            db.refresh(workflow_catalog)
            
            results["created"].append({
                "id": str(workflow_catalog.id),
                "filename": filename,
                "subflow_key": subflow_key,
                "version": version,
                "process_id": process_id,
                "published": workflow_catalog.published,
            })
            
        except Exception as e:
            db.rollback()
            results["errors"].append({
                "filename": filename,
                "error": str(e)
            })
    
    return {
        "message": "Workflow catalog seeding completed",
        "total_files": len(bpmn_files),
        "created_count": len(results["created"]),
        "skipped_count": len(results["skipped"]),
        "error_count": len(results["errors"]),
        "details": results,
    }


@seed_router.get("/workflow-catalog/preview")
def preview_bpmn_files(
    current_user: User = Depends(require_super_admin),
):
    """
    Preview BPMN files that will be seeded.
    
    Shows what files exist and what process IDs they contain.
    Useful to check before running the seed operation.
    """
    if not os.path.exists(BPMN_DIR):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BPMN directory not found: {BPMN_DIR}",
        )
    
    bpmn_files = [f for f in os.listdir(BPMN_DIR) if f.endswith('.bpmn')]
    
    if not bpmn_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No BPMN files found in {BPMN_DIR}",
        )
    
    preview = []
    
    for filename in bpmn_files:
        try:
            filepath = os.path.join(BPMN_DIR, filename)
            
            # Read BPMN file
            with open(filepath, 'r', encoding='utf-8') as f:
                bpmn_xml = f.read()
            
            # Extract process information
            process_id = extract_process_id_from_bpmn(bpmn_xml)
            subflow_key = extract_subflow_key_from_process_id(process_id)
            version = extract_version_from_process_id(process_id)
            
            preview.append({
                "filename": filename,
                "filepath": filepath,
                "process_id": process_id,
                "subflow_key": subflow_key,
                "version": version,
                "file_size_bytes": len(bpmn_xml),
            })
            
        except Exception as e:
            preview.append({
                "filename": filename,
                "error": str(e)
            })
    
    return {
        "bpmn_directory": BPMN_DIR,
        "total_files": len(bpmn_files),
        "files": preview,
    }
