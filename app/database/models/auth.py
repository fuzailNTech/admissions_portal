import uuid
import enum
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum as SQLEnum, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.config.db import Base
from datetime import datetime, timedelta


class StaffRoleType(str, enum.Enum):
    """Staff role type enumeration."""
    
    INSTITUTE_ADMIN = "institute_admin"  # Full access to all campuses in institute
    CAMPUS_ADMIN = "campus_admin"        # Access to specific assigned campuses only


class User(Base):
    """User model for authentication."""
    
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    email = Column(String, unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    password_hash = Column(String, nullable=False)
    is_temporary_password = Column(Boolean, default=False, nullable=False)
    verified = Column(Boolean, default=False, nullable=False)
    is_super_admin = Column(Boolean, default=False, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    staff_profile = relationship(
        "StaffProfile",
        foreign_keys="StaffProfile.user_id",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    assigned_staff = relationship(
        "StaffProfile",
        foreign_keys="StaffProfile.assigned_by",
        back_populates="assigner",
    )
    student_profile = relationship(
        "StudentProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )


class StaffProfile(Base):
    """Staff profile with institute/campus access."""
    
    __tablename__ = "staff_profiles"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=True)
    profile_picture_url = Column(String, nullable=True)
    role = Column(
        SQLEnum(StaffRoleType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    institute_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    assigned_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="staff_profile")
    institute = relationship("Institute", back_populates="staff_profiles")
    campus_assignments = relationship("StaffCampus", back_populates="staff_profile", cascade="all, delete-orphan")
    assigner = relationship("User", foreign_keys=[assigned_by], back_populates="assigned_staff")

    # Indexes
    __table_args__ = (
        Index("ix_staff_profile_institute_active", "institute_id", "is_active"),
        Index("ix_staff_profile_role_institute", "role", "institute_id", "is_active"),
    )


class StaffCampus(Base):
    """Junction table for Campus Admin assignments to specific campuses."""
    
    __tablename__ = "staff_campuses"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    staff_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campus_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campuses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_active = Column(Boolean, default=True, nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    staff_profile = relationship("StaffProfile", back_populates="campus_assignments")
    campus = relationship("Campus", back_populates="staff_assignments")

    # Constraints
    __table_args__ = (
        UniqueConstraint("staff_profile_id", "campus_id", name="uq_staff_campus"),
        Index("ix_staff_campus_active", "staff_profile_id", "is_active"),
        Index("ix_campus_staff_active", "campus_id", "is_active"),
    )


