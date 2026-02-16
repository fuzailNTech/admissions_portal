"""convert_enums_to_lowercase

Revision ID: bf6f233c8711
Revises: 89dfb408ecf4
Create Date: 2026-02-16 23:41:00.162974

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bf6f233c8711'
down_revision: Union[str, Sequence[str], None] = '89dfb408ecf4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Convert all enum types from UPPERCASE to lowercase."""
    
    # Institute enums
    op.execute("ALTER TYPE institutetype RENAME TO institutetype_old")
    op.execute("CREATE TYPE institutetype AS ENUM ('government', 'private', 'semi_government')")
    op.execute("ALTER TABLE institutes ALTER COLUMN institute_type TYPE institutetype USING LOWER(institute_type::text)::institutetype")
    op.execute("DROP TYPE institutetype_old")
    
    op.execute("ALTER TYPE institutestatus RENAME TO institutestatus_old")
    op.execute("CREATE TYPE institutestatus AS ENUM ('active', 'inactive', 'suspended', 'pending_approval')")
    op.execute("ALTER TABLE institutes ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE institutes ALTER COLUMN status TYPE institutestatus USING LOWER(status::text)::institutestatus")
    op.execute("ALTER TABLE institutes ALTER COLUMN status SET DEFAULT 'active'")
    op.execute("DROP TYPE institutestatus_old")
    
    op.execute("ALTER TYPE institutelevel RENAME TO institutelevel_old")
    op.execute("CREATE TYPE institutelevel AS ENUM ('university', 'college', 'institute', 'school')")
    op.execute("ALTER TABLE institutes ALTER COLUMN institute_level TYPE institutelevel USING LOWER(institute_level::text)::institutelevel")
    op.execute("DROP TYPE institutelevel_old")
    
    # Campus enums
    op.execute("ALTER TYPE campustype RENAME TO campustype_old")
    op.execute("CREATE TYPE campustype AS ENUM ('boys', 'girls', 'co_ed')")
    op.execute("ALTER TABLE campuses ALTER COLUMN campus_type TYPE campustype USING LOWER(campus_type::text)::campustype")
    op.execute("DROP TYPE campustype_old")
    
    # Program enum
    op.execute("ALTER TYPE shifttype RENAME TO shifttype_old")
    op.execute("CREATE TYPE shifttype AS ENUM ('morning', 'afternoon', 'evening')")
    op.execute("ALTER TABLE programs ALTER COLUMN shift DROP DEFAULT")
    op.execute("ALTER TABLE programs ALTER COLUMN shift TYPE shifttype USING LOWER(shift::text)::shifttype")
    op.execute("ALTER TABLE programs ALTER COLUMN shift SET DEFAULT 'morning'")
    op.execute("DROP TYPE shifttype_old")
    
    # Staff enum
    op.execute("ALTER TYPE staffroletype RENAME TO staffroletype_old")
    op.execute("CREATE TYPE staffroletype AS ENUM ('institute_admin', 'campus_admin')")
    op.execute("ALTER TABLE staff_profiles ALTER COLUMN role TYPE staffroletype USING LOWER(role::text)::staffroletype")
    op.execute("DROP TYPE staffroletype_old")
    
    # Admission enums
    op.execute("ALTER TYPE academicsession RENAME TO academicsession_old")
    op.execute("CREATE TYPE academicsession AS ENUM ('spring', 'fall', 'annual', 'summer')")
    op.execute("ALTER TABLE admission_cycles ALTER COLUMN session DROP DEFAULT")
    op.execute("ALTER TABLE admission_cycles ALTER COLUMN session TYPE academicsession USING LOWER(session::text)::academicsession")
    op.execute("ALTER TABLE admission_cycles ALTER COLUMN session SET DEFAULT 'annual'")
    op.execute("DROP TYPE academicsession_old")
    
    op.execute("ALTER TYPE admissioncyclestatus RENAME TO admissioncyclestatus_old")
    op.execute("CREATE TYPE admissioncyclestatus AS ENUM ('draft', 'upcoming', 'open', 'closed', 'completed', 'cancelled')")
    op.execute("ALTER TABLE admission_cycles ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE admission_cycles ALTER COLUMN status TYPE admissioncyclestatus USING LOWER(status::text)::admissioncyclestatus")
    op.execute("ALTER TABLE admission_cycles ALTER COLUMN status SET DEFAULT 'draft'")
    op.execute("DROP TYPE admissioncyclestatus_old")
    
    op.execute("ALTER TYPE quotatype RENAME TO quotatype_old")
    op.execute("CREATE TYPE quotatype AS ENUM ('open_merit', 'hafiz_e_quran', 'sports', 'minority', 'district_reserved', 'sibling', 'employee_children', 'disabled', 'overseas_pakistani', 'defense_forces', 'custom')")
    op.execute("ALTER TABLE program_quotas ALTER COLUMN quota_type TYPE quotatype USING LOWER(quota_type::text)::quotatype")
    op.execute("DROP TYPE quotatype_old")
    
    op.execute("ALTER TYPE quotastatus RENAME TO quotastatus_old")
    op.execute("CREATE TYPE quotastatus AS ENUM ('active', 'filled', 'suspended')")
    op.execute("ALTER TABLE program_quotas ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE program_quotas ALTER COLUMN status TYPE quotastatus USING LOWER(status::text)::quotastatus")
    op.execute("ALTER TABLE program_quotas ALTER COLUMN status SET DEFAULT 'active'")
    op.execute("DROP TYPE quotastatus_old")
    
    op.execute("ALTER TYPE fieldtype RENAME TO fieldtype_old")
    op.execute("CREATE TYPE fieldtype AS ENUM ('text', 'textarea', 'number', 'email', 'tel', 'date', 'select', 'radio', 'checkbox', 'file')")
    op.execute("ALTER TABLE custom_form_fields ALTER COLUMN field_type TYPE fieldtype USING LOWER(field_type::text)::fieldtype")
    op.execute("DROP TYPE fieldtype_old")
    
    # Student enums
    op.execute("ALTER TYPE gendertype RENAME TO gendertype_old")
    op.execute("CREATE TYPE gendertype AS ENUM ('male', 'female', 'other')")
    op.execute("ALTER TABLE student_profiles ALTER COLUMN gender TYPE gendertype USING LOWER(gender::text)::gendertype")
    op.execute("DROP TYPE gendertype_old")
    
    op.execute("ALTER TYPE identitydocumenttype RENAME TO identitydocumenttype_old")
    op.execute("CREATE TYPE identitydocumenttype AS ENUM ('cnic', 'b_form')")
    op.execute("ALTER TABLE student_profiles ALTER COLUMN identity_doc_type TYPE identitydocumenttype USING LOWER(identity_doc_type::text)::identitydocumenttype")
    op.execute("DROP TYPE identitydocumenttype_old")
    
    op.execute("ALTER TYPE religiontype RENAME TO religiontype_old")
    op.execute("CREATE TYPE religiontype AS ENUM ('islam', 'christianity', 'hinduism', 'sikhism', 'other')")
    op.execute("ALTER TABLE student_profiles ALTER COLUMN religion TYPE religiontype USING LOWER(religion::text)::religiontype")
    op.execute("DROP TYPE religiontype_old")
    
    op.execute("ALTER TYPE provincetype RENAME TO provincetype_old")
    op.execute("CREATE TYPE provincetype AS ENUM ('punjab', 'sindh', 'khyber_pakhtunkhwa', 'balochistan', 'gilgit_baltistan', 'azad_jammu_kashmir', 'islamabad_capital_territory', 'fata')")
    op.execute("ALTER TABLE student_profiles ALTER COLUMN province TYPE provincetype USING LOWER(province::text)::provincetype")
    op.execute("ALTER TABLE student_profiles ALTER COLUMN domicile_province TYPE provincetype USING LOWER(domicile_province::text)::provincetype")
    op.execute("DROP TYPE provincetype_old")
    
    op.execute("ALTER TYPE guardianrelationship RENAME TO guardianrelationship_old")
    op.execute("CREATE TYPE guardianrelationship AS ENUM ('father', 'mother', 'brother', 'sister', 'uncle', 'aunt', 'grandfather', 'grandmother', 'legal_guardian', 'other')")
    op.execute("ALTER TABLE student_guardians ALTER COLUMN guardian_relationship TYPE guardianrelationship USING LOWER(guardian_relationship::text)::guardianrelationship")
    op.execute("DROP TYPE guardianrelationship_old")
    
    op.execute("ALTER TYPE academiclevel RENAME TO academiclevel_old")
    op.execute("CREATE TYPE academiclevel AS ENUM ('primary', 'middle', 'secondary', 'higher_secondary')")
    op.execute("ALTER TABLE student_academic_records ALTER COLUMN level TYPE academiclevel USING LOWER(level::text)::academiclevel")
    op.execute("DROP TYPE academiclevel_old")
    
    op.execute("ALTER TYPE educationgroup RENAME TO educationgroup_old")
    op.execute("CREATE TYPE educationgroup AS ENUM ('ssc_science_biology', 'ssc_science_computer', 'ssc_humanities', 'ssc_commerce', 'ssc_technical', 'ssc_agriculture', 'ssc_health_science', 'hssc_fsc_pre_medical', 'hssc_fsc_pre_engineering', 'hssc_fsc_general_science', 'hssc_ics', 'hssc_fa', 'hssc_icom', 'hssc_dcom', 'hssc_technical')")
    op.execute("ALTER TABLE student_academic_records ALTER COLUMN education_group TYPE educationgroup USING LOWER(education_group::text)::educationgroup")
    op.execute("DROP TYPE educationgroup_old")
    
    # Application enums
    op.execute("ALTER TYPE applicationstatus RENAME TO applicationstatus_old")
    op.execute("CREATE TYPE applicationstatus AS ENUM ('submitted', 'under_review', 'documents_pending', 'verified', 'offered', 'rejected', 'accepted', 'withdrawn')")
    op.execute("ALTER TABLE applications ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE applications ALTER COLUMN status TYPE applicationstatus USING LOWER(status::text)::applicationstatus")
    op.execute("ALTER TABLE applications ALTER COLUMN status SET DEFAULT 'submitted'")
    op.execute("ALTER TABLE application_status_history ALTER COLUMN from_status TYPE applicationstatus USING LOWER(from_status::text)::applicationstatus")
    op.execute("ALTER TABLE application_status_history ALTER COLUMN to_status TYPE applicationstatus USING LOWER(to_status::text)::applicationstatus")
    op.execute("DROP TYPE applicationstatus_old")
    
    op.execute("ALTER TYPE verificationstatus RENAME TO verificationstatus_old")
    op.execute("CREATE TYPE verificationstatus AS ENUM ('pending', 'approved', 'rejected')")
    op.execute("ALTER TABLE application_academic_snapshots ALTER COLUMN verification_status DROP DEFAULT")
    op.execute("ALTER TABLE application_academic_snapshots ALTER COLUMN verification_status TYPE verificationstatus USING LOWER(verification_status::text)::verificationstatus")
    op.execute("ALTER TABLE application_academic_snapshots ALTER COLUMN verification_status SET DEFAULT 'pending'")
    op.execute("ALTER TABLE application_documents ALTER COLUMN verification_status DROP DEFAULT")
    op.execute("ALTER TABLE application_documents ALTER COLUMN verification_status TYPE verificationstatus USING LOWER(verification_status::text)::verificationstatus")
    op.execute("ALTER TABLE application_documents ALTER COLUMN verification_status SET DEFAULT 'pending'")
    op.execute("DROP TYPE verificationstatus_old")


def downgrade() -> None:
    """Downgrade schema - Convert all enum types from lowercase back to UPPERCASE."""
    
    # Reverse all the conversions
    op.execute("ALTER TYPE verificationstatus RENAME TO verificationstatus_old")
    op.execute("CREATE TYPE verificationstatus AS ENUM ('PENDING', 'APPROVED', 'REJECTED')")
    op.execute("ALTER TABLE application_documents ALTER COLUMN verification_status DROP DEFAULT")
    op.execute("ALTER TABLE application_documents ALTER COLUMN verification_status TYPE verificationstatus USING UPPER(verification_status::text)::verificationstatus")
    op.execute("ALTER TABLE application_documents ALTER COLUMN verification_status SET DEFAULT 'PENDING'")
    op.execute("ALTER TABLE application_academic_snapshots ALTER COLUMN verification_status DROP DEFAULT")
    op.execute("ALTER TABLE application_academic_snapshots ALTER COLUMN verification_status TYPE verificationstatus USING UPPER(verification_status::text)::verificationstatus")
    op.execute("ALTER TABLE application_academic_snapshots ALTER COLUMN verification_status SET DEFAULT 'PENDING'")
    op.execute("DROP TYPE verificationstatus_old")
    
    op.execute("ALTER TYPE applicationstatus RENAME TO applicationstatus_old")
    op.execute("CREATE TYPE applicationstatus AS ENUM ('SUBMITTED', 'UNDER_REVIEW', 'DOCUMENTS_PENDING', 'VERIFIED', 'OFFERED', 'REJECTED', 'ACCEPTED', 'WITHDRAWN')")
    op.execute("ALTER TABLE application_status_history ALTER COLUMN to_status TYPE applicationstatus USING UPPER(to_status::text)::applicationstatus")
    op.execute("ALTER TABLE application_status_history ALTER COLUMN from_status TYPE applicationstatus USING UPPER(from_status::text)::applicationstatus")
    op.execute("ALTER TABLE applications ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE applications ALTER COLUMN status TYPE applicationstatus USING UPPER(status::text)::applicationstatus")
    op.execute("ALTER TABLE applications ALTER COLUMN status SET DEFAULT 'SUBMITTED'")
    op.execute("DROP TYPE applicationstatus_old")
    
    op.execute("ALTER TYPE educationgroup RENAME TO educationgroup_old")
    op.execute("CREATE TYPE educationgroup AS ENUM ('SSC_SCIENCE_BIOLOGY', 'SSC_SCIENCE_COMPUTER', 'SSC_HUMANITIES', 'SSC_COMMERCE', 'SSC_TECHNICAL', 'SSC_AGRICULTURE', 'SSC_HEALTH_SCIENCE', 'HSSC_FSC_PRE_MEDICAL', 'HSSC_FSC_PRE_ENGINEERING', 'HSSC_FSC_GENERAL_SCIENCE', 'HSSC_ICS', 'HSSC_FA', 'HSSC_ICOM', 'HSSC_DCOM', 'HSSC_TECHNICAL')")
    op.execute("ALTER TABLE student_academic_records ALTER COLUMN education_group TYPE educationgroup USING UPPER(education_group::text)::educationgroup")
    op.execute("DROP TYPE educationgroup_old")
    
    op.execute("ALTER TYPE academiclevel RENAME TO academiclevel_old")
    op.execute("CREATE TYPE academiclevel AS ENUM ('PRIMARY', 'MIDDLE', 'SECONDARY', 'HIGHER_SECONDARY')")
    op.execute("ALTER TABLE student_academic_records ALTER COLUMN level TYPE academiclevel USING UPPER(level::text)::academiclevel")
    op.execute("DROP TYPE academiclevel_old")
    
    op.execute("ALTER TYPE guardianrelationship RENAME TO guardianrelationship_old")
    op.execute("CREATE TYPE guardianrelationship AS ENUM ('FATHER', 'MOTHER', 'BROTHER', 'SISTER', 'UNCLE', 'AUNT', 'GRANDFATHER', 'GRANDMOTHER', 'LEGAL_GUARDIAN', 'OTHER')")
    op.execute("ALTER TABLE student_guardians ALTER COLUMN guardian_relationship TYPE guardianrelationship USING UPPER(guardian_relationship::text)::guardianrelationship")
    op.execute("DROP TYPE guardianrelationship_old")
    
    op.execute("ALTER TYPE provincetype RENAME TO provincetype_old")
    op.execute("CREATE TYPE provincetype AS ENUM ('PUNJAB', 'SINDH', 'KPK', 'BALOCHISTAN', 'GILGIT_BALTISTAN', 'AJK', 'ICT', 'FATA')")
    op.execute("ALTER TABLE student_profiles ALTER COLUMN domicile_province TYPE provincetype USING UPPER(domicile_province::text)::provincetype")
    op.execute("ALTER TABLE student_profiles ALTER COLUMN province TYPE provincetype USING UPPER(province::text)::provincetype")
    op.execute("DROP TYPE provincetype_old")
    
    op.execute("ALTER TYPE religiontype RENAME TO religiontype_old")
    op.execute("CREATE TYPE religiontype AS ENUM ('ISLAM', 'CHRISTIANITY', 'HINDUISM', 'SIKHISM', 'OTHER')")
    op.execute("ALTER TABLE student_profiles ALTER COLUMN religion TYPE religiontype USING UPPER(religion::text)::religiontype")
    op.execute("DROP TYPE religiontype_old")
    
    op.execute("ALTER TYPE identitydocumenttype RENAME TO identitydocumenttype_old")
    op.execute("CREATE TYPE identitydocumenttype AS ENUM ('CNIC', 'B_FORM')")
    op.execute("ALTER TABLE student_profiles ALTER COLUMN identity_doc_type TYPE identitydocumenttype USING UPPER(identity_doc_type::text)::identitydocumenttype")
    op.execute("DROP TYPE identitydocumenttype_old")
    
    op.execute("ALTER TYPE gendertype RENAME TO gendertype_old")
    op.execute("CREATE TYPE gendertype AS ENUM ('MALE', 'FEMALE', 'OTHER')")
    op.execute("ALTER TABLE student_profiles ALTER COLUMN gender TYPE gendertype USING UPPER(gender::text)::gendertype")
    op.execute("DROP TYPE gendertype_old")
    
    op.execute("ALTER TYPE fieldtype RENAME TO fieldtype_old")
    op.execute("CREATE TYPE fieldtype AS ENUM ('TEXT', 'TEXTAREA', 'NUMBER', 'EMAIL', 'TEL', 'DATE', 'SELECT', 'RADIO', 'CHECKBOX', 'FILE')")
    op.execute("ALTER TABLE custom_form_fields ALTER COLUMN field_type TYPE fieldtype USING UPPER(field_type::text)::fieldtype")
    op.execute("DROP TYPE fieldtype_old")
    
    op.execute("ALTER TYPE quotastatus RENAME TO quotastatus_old")
    op.execute("CREATE TYPE quotastatus AS ENUM ('ACTIVE', 'FILLED', 'SUSPENDED')")
    op.execute("ALTER TABLE program_quotas ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE program_quotas ALTER COLUMN status TYPE quotastatus USING UPPER(status::text)::quotastatus")
    op.execute("ALTER TABLE program_quotas ALTER COLUMN status SET DEFAULT 'ACTIVE'")
    op.execute("DROP TYPE quotastatus_old")
    
    op.execute("ALTER TYPE quotatype RENAME TO quotatype_old")
    op.execute("CREATE TYPE quotatype AS ENUM ('OPEN_MERIT', 'HAFIZ_E_QURAN', 'SPORTS', 'MINORITY', 'DISTRICT_RESERVED', 'SIBLING', 'EMPLOYEE_CHILDREN', 'DISABLED', 'OVERSEAS_PAKISTANI', 'DEFENSE_FORCES', 'CUSTOM')")
    op.execute("ALTER TABLE program_quotas ALTER COLUMN quota_type TYPE quotatype USING UPPER(quota_type::text)::quotatype")
    op.execute("DROP TYPE quotatype_old")
    
    op.execute("ALTER TYPE admissioncyclestatus RENAME TO admissioncyclestatus_old")
    op.execute("CREATE TYPE admissioncyclestatus AS ENUM ('DRAFT', 'UPCOMING', 'OPEN', 'CLOSED', 'COMPLETED', 'CANCELLED')")
    op.execute("ALTER TABLE admission_cycles ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE admission_cycles ALTER COLUMN status TYPE admissioncyclestatus USING UPPER(status::text)::admissioncyclestatus")
    op.execute("ALTER TABLE admission_cycles ALTER COLUMN status SET DEFAULT 'DRAFT'")
    op.execute("DROP TYPE admissioncyclestatus_old")
    
    op.execute("ALTER TYPE academicsession RENAME TO academicsession_old")
    op.execute("CREATE TYPE academicsession AS ENUM ('SPRING', 'FALL', 'ANNUAL', 'SUMMER')")
    op.execute("ALTER TABLE admission_cycles ALTER COLUMN session DROP DEFAULT")
    op.execute("ALTER TABLE admission_cycles ALTER COLUMN session TYPE academicsession USING UPPER(session::text)::academicsession")
    op.execute("ALTER TABLE admission_cycles ALTER COLUMN session SET DEFAULT 'ANNUAL'")
    op.execute("DROP TYPE academicsession_old")
    
    op.execute("ALTER TYPE staffroletype RENAME TO staffroletype_old")
    op.execute("CREATE TYPE staffroletype AS ENUM ('INSTITUTE_ADMIN', 'CAMPUS_ADMIN')")
    op.execute("ALTER TABLE staff_profiles ALTER COLUMN role TYPE staffroletype USING UPPER(role::text)::staffroletype")
    op.execute("DROP TYPE staffroletype_old")
    
    op.execute("ALTER TYPE shifttype RENAME TO shifttype_old")
    op.execute("CREATE TYPE shifttype AS ENUM ('MORNING', 'AFTERNOON', 'EVENING')")
    op.execute("ALTER TABLE programs ALTER COLUMN shift DROP DEFAULT")
    op.execute("ALTER TABLE programs ALTER COLUMN shift TYPE shifttype USING UPPER(shift::text)::shifttype")
    op.execute("ALTER TABLE programs ALTER COLUMN shift SET DEFAULT 'MORNING'")
    op.execute("DROP TYPE shifttype_old")
    
    op.execute("ALTER TYPE campustype RENAME TO campustype_old")
    op.execute("CREATE TYPE campustype AS ENUM ('BOYS', 'GIRLS', 'CO_ED')")
    op.execute("ALTER TABLE campuses ALTER COLUMN campus_type TYPE campustype USING UPPER(campus_type::text)::campustype")
    op.execute("DROP TYPE campustype_old")
    
    op.execute("ALTER TYPE institutelevel RENAME TO institutelevel_old")
    op.execute("CREATE TYPE institutelevel AS ENUM ('UNIVERSITY', 'COLLEGE', 'INSTITUTE', 'SCHOOL')")
    op.execute("ALTER TABLE institutes ALTER COLUMN institute_level TYPE institutelevel USING UPPER(institute_level::text)::institutelevel")
    op.execute("DROP TYPE institutelevel_old")
    
    op.execute("ALTER TYPE institutestatus RENAME TO institutestatus_old")
    op.execute("CREATE TYPE institutestatus AS ENUM ('ACTIVE', 'INACTIVE', 'SUSPENDED', 'PENDING_APPROVAL')")
    op.execute("ALTER TABLE institutes ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE institutes ALTER COLUMN status TYPE institutestatus USING UPPER(status::text)::institutestatus")
    op.execute("ALTER TABLE institutes ALTER COLUMN status SET DEFAULT 'ACTIVE'")
    op.execute("DROP TYPE institutestatus_old")
    
    op.execute("ALTER TYPE institutetype RENAME TO institutetype_old")
    op.execute("CREATE TYPE institutetype AS ENUM ('GOVERNMENT', 'PRIVATE', 'SEMI_GOVERNMENT')")
    op.execute("ALTER TABLE institutes ALTER COLUMN institute_type TYPE institutetype USING UPPER(institute_type::text)::institutetype")
    op.execute("DROP TYPE institutetype_old")
