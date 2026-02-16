"""
Admission-related utility functions
"""
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.database.models.admission import AdmissionCycle, AdmissionCycleStatus
from app.database.models.application import ApplicationNumberSequence
from app.database.models.institute import Institute


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
            AdmissionCycle.status.in_([AdmissionCycleStatus.OPEN, AdmissionCycleStatus.UPCOMING])
        )
        .order_by(AdmissionCycle.application_start_date.desc())
        .first()
    )


def generate_application_number(
    db: Session,
    institute_id: UUID,
    academic_year: str
) -> str:
    """
    Generate a unique application number for an institute and academic year.
    
    Format: {INSTITUTE_CODE}-{ACADEMIC_YEAR}-{SEQUENTIAL_NUMBER}
    Example: PGC-2026-00001
    
    Uses row-level locking (SELECT FOR UPDATE) to prevent race conditions
    when multiple applications are submitted simultaneously.
    
    Args:
        db: Database session (must be in an active transaction)
        institute_id: UUID of the institute
        academic_year: Academic year (e.g., "2026" or "2026-27")
        
    Returns:
        Formatted application number string
        
    Raises:
        ValueError: If institute not found or institute_code not set
    """
    # Get institute code
    institute = db.query(Institute).filter(Institute.id == institute_id).first()
    if not institute:
        raise ValueError(f"Institute with id {institute_id} not found")
    
    if not institute.institute_code:
        raise ValueError(f"Institute {institute.name} does not have an institute_code set")
    
    # Get or create sequence record with row-level lock (FOR UPDATE)
    # This prevents concurrent transactions from getting the same number
    sequence = (
        db.query(ApplicationNumberSequence)
        .filter(
            ApplicationNumberSequence.institute_id == institute_id,
            ApplicationNumberSequence.academic_year == academic_year
        )
        .with_for_update()  # Row-level lock - critical for preventing duplicates
        .first()
    )
    
    if not sequence:
        # Create new sequence starting at 0
        sequence = ApplicationNumberSequence(
            institute_id=institute_id,
            academic_year=academic_year,
            last_number=0
        )
        db.add(sequence)
        db.flush()  # Get the sequence record into the session
    
    # Increment the counter
    sequence.last_number += 1
    sequential_number = sequence.last_number
    
    # Format: INST-YEAR-NNNNN (5 digits, zero-padded)
    application_number = f"{institute.institute_code}-{academic_year}-{sequential_number:05d}"
    
    # Note: Don't commit here - let the caller commit the entire transaction
    # This ensures atomicity with the application creation
    
    return application_number
