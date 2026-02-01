from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database.config.db import get_db
from app.database.models.auth import User, StaffProfile, StaffCampus, StaffRoleType
from app.database.models.institute import Institute, Campus
from app.settings import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_ACCESS_TOKEN_EXPIRE_MINUTES

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from JWT token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    if not user.verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not verified",
        )
    
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get the current active user (wrapper for get_current_user).
    """
    return current_user


# ==================== RBAC HELPER FUNCTIONS ====================

def get_current_staff(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> StaffProfile:
    """
    Get the current staff profile.
    Raises 403 if user doesn't have an active staff profile.
    
    Use this as a dependency to ensure user is staff.
    """
    staff_profile = db.query(StaffProfile).filter(
        StaffProfile.user_id == current_user.id
    ).first()
    
    if not staff_profile or not staff_profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required",
        )
    
    return staff_profile


def is_super_admin(user: User) -> bool:
    """
    Check if user is a super admin.
    
    Args:
        user: User object
        
    Returns:
        True if user is super admin and active, False otherwise
    """
    return user.is_super_admin and user.is_active


def require_super_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to require super admin access.
    
    Usage:
        @router.get("/endpoint")
        def endpoint(user: User = Depends(require_super_admin)):
            ...
    """
    if not is_super_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return current_user


def is_institute_admin(
    current_staff: StaffProfile = Depends(get_current_staff)
) -> StaffProfile:
    """
    Dependency to require institute admin role.
    
    Usage:
        @router.get("/endpoint")
        def endpoint(staff: StaffProfile = Depends(is_institute_admin)):
            # staff.institute_id gives you the institute
            ...
    """
    if current_staff.role != StaffRoleType.INSTITUTE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Institute admin access required",
        )
    return current_staff


def is_campus_admin(
    current_staff: StaffProfile = Depends(get_current_staff)
) -> StaffProfile:
    """
    Dependency to require campus admin role.
    
    Usage:
        @router.get("/endpoint")
        def endpoint(staff: StaffProfile = Depends(is_campus_admin)):
            # Use get_accessible_campuses to get their campuses
            ...
    """
    if current_staff.role != StaffRoleType.CAMPUS_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Campus admin access required",
        )
    return current_staff


def get_user_institute(
    staff: StaffProfile,
    db: Session
) -> Optional[Institute]:
    """
    Get the institute for a staff member.
    
    Args:
        staff: StaffProfile object
        db: Database session
        
    Returns:
        Institute object or None if not found
        
    Usage:
        institute = get_user_institute(staff, db)
        if not institute:
            raise HTTPException(404, "Institute not found")
    """
    return db.query(Institute).filter(
        Institute.id == staff.institute_id
    ).first()


def get_accessible_campuses(
    staff: StaffProfile,
    db: Session
) -> List[Campus]:
    """
    Get all campuses accessible by a staff member.
    
    - Institute Admin: Returns ALL campuses in their institute
    - Campus Admin: Returns ONLY assigned campuses
    
    Args:
        staff: StaffProfile object
        db: Database session
        
    Returns:
        List of Campus objects
        
    Usage:
        campuses = get_accessible_campuses(staff, db)
        for campus in campuses:
            print(campus.name)
    """
    if staff.role == StaffRoleType.INSTITUTE_ADMIN:
        # Institute admin has access to all campuses in their institute
        return db.query(Campus).filter(
            Campus.institute_id == staff.institute_id,
            Campus.is_active == True
        ).all()
    
    elif staff.role == StaffRoleType.CAMPUS_ADMIN:
        # Campus admin has access only to assigned campuses
        return db.query(Campus).join(StaffCampus).filter(
            StaffCampus.staff_profile_id == staff.id,
            StaffCampus.is_active == True,
            Campus.is_active == True
        ).all()
    
    return []


def can_access_institute(
    institute_id: UUID,
    current_staff: StaffProfile,
) -> bool:
    """
    Check if staff member can access a specific institute.
    
    Args:
        institute_id: UUID of the institute to check
        current_staff: StaffProfile object
        
    Returns:
        True if staff can access the institute, False otherwise
    """
    return current_staff.institute_id == institute_id


def can_access_campus(
    campus_id: UUID,
    current_staff: StaffProfile,
    db: Session
) -> bool:
    """
    Check if staff member can access a specific campus.
    
    Args:
        campus_id: UUID of the campus to check
        current_staff: StaffProfile object
        db: Database session
        
    Returns:
        True if staff can access the campus, False otherwise
    """
    # Get the campus to check its institute
    campus = db.query(Campus).filter(Campus.id == campus_id).first()
    if not campus:
        return False
    
    # Staff must belong to the same institute
    if campus.institute_id != current_staff.institute_id:
        return False
    
    # Institute admin has access to all campuses in their institute
    if current_staff.role == StaffRoleType.INSTITUTE_ADMIN:
        return True
    
    # Campus admin needs explicit assignment
    if current_staff.role == StaffRoleType.CAMPUS_ADMIN:
        assignment = db.query(StaffCampus).filter(
            StaffCampus.staff_profile_id == current_staff.id,
            StaffCampus.campus_id == campus_id,
            StaffCampus.is_active == True
        ).first()
        return assignment is not None
    
    return False


def require_institute_access(institute_id: UUID):
    """
    Dependency factory to require access to a specific institute.
    
    Usage:
        @router.get("/institutes/{institute_id}/endpoint")
        def endpoint(
            institute_id: UUID,
            staff: StaffProfile = Depends(require_institute_access(institute_id))
        ):
            ...
    """
    def check_access(
        current_staff: StaffProfile = Depends(get_current_staff)
    ) -> StaffProfile:
        if not can_access_institute(institute_id, current_staff):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this institute",
            )
        return current_staff
    
    return check_access


def require_campus_access(campus_id: UUID):
    """
    Dependency factory to require access to a specific campus.
    
    Usage:
        @router.get("/campuses/{campus_id}/endpoint")
        def endpoint(
            campus_id: UUID,
            staff: StaffProfile = Depends(require_campus_access(campus_id))
        ):
            ...
    """
    def check_access(
        current_staff: StaffProfile = Depends(get_current_staff),
        db: Session = Depends(get_db)
    ) -> StaffProfile:
        if not can_access_campus(campus_id, current_staff, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this campus",
            )
        return current_staff
    
    return check_access


