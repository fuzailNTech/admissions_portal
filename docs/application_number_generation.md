# Application Number Generation

## Overview

Application numbers are generated using a sequential counter per institute per academic year.

**Format:** `{INSTITUTE_CODE}-{ACADEMIC_YEAR}-{SEQUENTIAL_NUMBER}`

**Examples:**
- `PGC-2026-00001`
- `PGC-2026-00002`
- `GCU-2026-00847`

## Database Table

### `application_number_sequences`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `institute_id` | UUID | FK to institutes table |
| `academic_year` | VARCHAR(10) | Academic year (e.g., "2026" or "2026-27") |
| `last_number` | INTEGER | Current counter value |
| `created_at` | TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | Last update time |

**Constraints:**
- Unique constraint on `(institute_id, academic_year)`
- Index on `(institute_id, academic_year)` for fast lookups

## Usage

### In Application Submission Flow

```python
from app.utils.admission import generate_application_number
from sqlalchemy.orm import Session

def create_application(db: Session, data):
    # Must be within a transaction
    with db.begin():
        # ... other application creation logic ...
        
        # Generate application number
        application_number = generate_application_number(
            db=db,
            institute_id=institute_id,
            academic_year="2026"  # or "2026-27"
        )
        
        # Create application with generated number
        application = Application(
            application_number=application_number,
            # ... other fields ...
        )
        db.add(application)
        
        # Commit happens at end of with block
```

### Important Notes

1. **Transaction Required**: Must be called within an active database transaction
2. **Row-Level Locking**: Uses `SELECT FOR UPDATE` to prevent race conditions
3. **Atomic**: Number generation and application creation are atomic
4. **No Manual Commit**: Let the outer transaction handle the commit
5. **Thread-Safe**: Safe for concurrent application submissions

## How It Works

1. **First Time (New Year/Institute)**:
   - Creates sequence record with `last_number = 0`
   - Increments to 1
   - Returns: `PGC-2026-00001`

2. **Subsequent Calls**:
   - Locks existing sequence record (`SELECT FOR UPDATE`)
   - Increments `last_number` by 1
   - Returns formatted number
   - Lock released on commit

3. **Concurrency Safety**:
   - Transaction A locks sequence, gets number 5
   - Transaction B waits for lock
   - Transaction A commits
   - Transaction B gets lock, gets number 6
   - No collisions possible

## Example Sequence

```
Institute: Punjab Group of Colleges (PGC)
Academic Year: 2026

PGC-2026-00001  ← First application
PGC-2026-00002  ← Second application
PGC-2026-00003  ← Third application
...
PGC-2026-01234  ← 1,234th application
```

## Prerequisites

### Institute Must Have Code

The institute must have `institute_code` set:

```python
institute = Institute(
    name="Punjab Group of Colleges",
    institute_code="PGC",  # ← Required for application number generation
    # ... other fields ...
)
```

### Academic Year Format

Academic year can be:
- Single year: `"2026"`
- Range: `"2026-27"`
- Extracted from `AdmissionCycle.academic_year`

## Error Handling

```python
try:
    app_number = generate_application_number(db, institute_id, academic_year)
except ValueError as e:
    # Institute not found or institute_code not set
    print(f"Error: {e}")
```

## Migration

To set up the table, create a migration:

```bash
alembic revision -m "add_application_number_sequences_table"
```

The migration should create the table with proper indexes and constraints as defined in the model.
