# GIKI Sports Complex — Facility & Schedule Data Model Specification

## 1. Architectural Overview & System Design

The Sports Complex management subsystem enables the **Sports Director** and **Super Administrators** to dynamically manage campus facilities and their recurring weekly operating windows.

### Core Software Engineering Principles
1. **Dynamic Facility Administration**: The Director is not constrained by hardcoded facilities or static configuration files. New sporting arenas can be added, and existing ones updated live without downtime or database re-seeding.
2. **Immutable Identity vs. Mutable Presentation**:
   - The primary identifier (`id` UUID) is immutable.
   - The URL slug (`slug` VARCHAR(100)) is unique and used as the canonical URL parameter.
   - Facility attributes (`name`, `description`, `status`) are fully mutable by authorized administrators.
3. **Domain Simplification & Single-Story Complex Architecture**:
   - All sports facilities are located inside or directly adjacent to the dedicated single-story GIKI Sports Complex building.
   - Granular `location` tags (e.g. "Wing B", "Ground Floor") were redundant cognitive noise and have been dropped cleanly from the database schema, backend models, APIs, and administrative UI forms.
4. **Operational State Machine Over Hard Deletes**:
   - Facilities reference downstream bookings and schedule windows with `ON DELETE RESTRICT`.
   - Deleting a facility is avoided in production to preserve historical booking records, wallet transactions, and audit trails.
   - Instead, facilities transition between three operational statuses: `active`, `maintenance`, and `closed`.
5. **Mandatory Administrative Audit Trails (FR-09)**:
   - All mutations (`facility.create`, `facility.update`, `schedule.create`, `schedule.update`, `schedule.delete`) execute inside atomic database transactions (`Begin` -> mutation -> audit log insert -> `Commit`).
   - If either the mutation or the audit log entry fails, the entire transaction rolls back.

---

## 2. Relational Database Schema

### `giki_sports.facilities`
```sql
CREATE TABLE IF NOT EXISTS giki_sports.facilities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_facilities_slug UNIQUE (slug),
    CONSTRAINT chk_facilities_slug_nonempty CHECK (length(trim(slug)) > 0),
    CONSTRAINT chk_facilities_name_nonempty CHECK (length(trim(name)) > 0),
    CONSTRAINT chk_facilities_status_valid CHECK (status IN ('active', 'maintenance', 'closed'))
);
```

### `giki_sports.schedules`
```sql
CREATE TABLE IF NOT EXISTS giki_sports.schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL,
    day_of_week SMALLINT NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    audience VARCHAR(50) NOT NULL DEFAULT 'general',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_schedules_facility FOREIGN KEY (facility_id) REFERENCES giki_sports.facilities(id) ON DELETE RESTRICT,
    CONSTRAINT chk_schedules_day_valid CHECK (day_of_week BETWEEN 1 AND 7),
    CONSTRAINT chk_schedules_time_order CHECK (start_time < end_time),
    CONSTRAINT chk_schedules_audience_valid CHECK (audience IN ('general', 'student', 'faculty', 'women_only', 'staff')),
    CONSTRAINT uq_schedules_window UNIQUE (facility_id, day_of_week, audience, start_time, end_time)
);
```

### `giki_sports.audit_logs`
```sql
CREATE TABLE IF NOT EXISTS giki_sports.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id UUID NOT NULL,
    details JSONB NOT NULL DEFAULT '{}',
    ip_address VARCHAR(45),
    user_agent TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_audit_logs_actor FOREIGN KEY (actor_id) REFERENCES giki_sports.users(id) ON DELETE RESTRICT,
    CONSTRAINT chk_audit_logs_action_nonempty CHECK (length(trim(action)) > 0),
    CONSTRAINT chk_audit_logs_target_type_nonempty CHECK (length(trim(target_type)) > 0),
    CONSTRAINT chk_audit_logs_status_valid CHECK (status IN ('SUCCESS', 'FAILURE'))
);
```

---

## 3. REST API Endpoints Specification

### 1. `POST /api/facilities` (Create Facility)
- **Role Requirement**: `sports_director`, `super_admin`
- **Request Headers**:
  - `Content-Type: application/json`
  - Origin / Cookie session
- **Request Payload**:
  ```json
  {
    "name": "Squash Complex",
    "slug": "squash-complex",
    "status": "active",
    "description": "Three ASB glass-backed squash courts with Junckers beechwood flooring."
  }
  ```
  - `name`: String (1..255 chars), mandatory.
  - `slug`: String (1..100 chars), optional. If omitted, auto-generated from `name` using `slugify()`. Must match `^[a-z0-9]+(?:-[a-z0-9]+)*$`.
  - `status`: String (`"active" | "maintenance" | "closed"`), optional (defaults to `"active"`).
  - `description`: String (<= 2000 chars), optional.
- **Responses**:
  - `201 Created`: Returns newly created `FacilityResponse` object.
  - `400 Bad Request`: Payload validation error (empty name, invalid status, malformed slug).
  - `409 Conflict`: A facility with the requested slug already exists.
  - `401 Unauthorized` / `403 Forbidden`: Unauthenticated or non-admin principal.

### 2. `PATCH /api/facilities/:slug` (Update Facility)
- **Role Requirement**: `sports_director`, `super_admin`
- **Request Payload**:
  ```json
  {
    "name": "Main Gymnasium",
    "status": "maintenance",
    "description": "Gymnasium is undergoing annual floor varnishing and barbell maintenance."
  }
  ```
  - At least one field (`name`, `status`, or `description`) must be provided.
- **Responses**:
  - `200 OK`: Returns updated `FacilityResponse` object with existing schedules.
  - `400 Bad Request`: Validation failure.
  - `404 Not Found`: Facility with provided slug does not exist.

### 3. `GET /api/facilities` (Public Directory)
- Returns array of all facilities with nested weekly operating schedules.

### 4. `GET /api/facilities/:slug` (Public Detail)
- Returns complete facility details with real-time operating status calculation.

---

## 4. Administrative Workflows in Frontend

### 1. Add Facility Workflow
1. When signed in as **Sports Director** or **Super Admin**, an `+ Add Facility` button appears in the Facilities directory section on the Home page (`FacilitiesGrid`).
2. Clicking the button opens `CreateFacilityModal`:
   - Live auto-slug generator derives URL slugs as the name is typed.
   - "Edit manually" toggle enables custom slug overrides.
   - Operational status selector with color-coded badges (`active`, `maintenance`, `closed`).
   - Description field with dynamic character counter (up to 2,000 characters).
3. Upon submission:
   - Client validates fields and submits `POST /api/facilities`.
   - On success, the modal closes and the directory updates immediately.

### 2. Edit Facility Workflow
1. When navigating to any facility detail page (`/facilities/:slug`), authorized administrators see the `Edit Facility` button in the hero banner.
2. Clicking the button opens `EditFacilityModal`, pre-filled with the current facility state.
3. The Director can adjust the name, operational status, or description.
4. On save:
   - Executes `PATCH /api/facilities/:slug`.
   - Live operating status badges and page title update immediately without full page reloads.
