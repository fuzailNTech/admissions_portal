"""
Admission-related utility functions
"""
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.database.models.admission import AdmissionCycle


def get_active_cycle(db: Session, institute_id: UUID) -> Optional[AdmissionCycle]:
    """
    Get the currently active/open admission cycle for an institute.
    
    Args:
        db: Database session
        institute_id: UUID of the institute
        
    Returns:
        Active AdmissionCycle or None if no active cycle exists
    """
    return (
        db.query(AdmissionCycle)
        .filter(
            AdmissionCycle.institute_id == institute_id,
            AdmissionCycle.is_published == True,
            AdmissionCycle.status.in_(["OPEN", "UPCOMING"])
        )
        .order_by(AdmissionCycle.application_start_date.desc())
        .first()
    )
