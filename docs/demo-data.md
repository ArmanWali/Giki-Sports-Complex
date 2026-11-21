# Demonstration Data Seeding Guide

This document describes the development demo seeding mechanism for the GIKI Sports Complex application.

---

## 1. Purpose & Separation of Concerns

### 1.1 Development Only
The seeding command is strictly intended for **local development and testing**. It populates a small, deterministic set of synthetic sports facilities and weekly recurring schedules so developers and testers can verify timetable rendering, card layouts, and query behaviors without entering records manually.

### 1.2 Demonstration Data vs. Institutional Policy
> [!IMPORTANT]
> **Synthetic Demonstration Notice:** All seeded facilities, descriptions, locations, weekdays, operating windows, and audience categories are synthetic demonstration fixtures labeled with `[Demo]`.
> **They do not represent institutionally approved GIKI sports complex facilities, timetables, gender policies, or fee structures.**

### 1.3 Schema Migrations vs. Demonstration Data
- **Schema Migrations (`backend/migrations/`):** Define the structural relational schema, constraints, data types, and indexes. Migrations run in all environments (development, staging, production) and must never contain transient or fake demo fixtures.
- **Demonstration Seeding (`backend/cmd/seed/`):** An explicit, opt-in developer tool that inserts demonstration fixtures into an already-migrated database. It is never executed automatically during container startup or migration runs.

---

## 2. Command Execution

### 2.1 Working Directory and Syntax

Run the command from the `backend/` directory:

```powershell
go run ./cmd/seed --demo
```

### 2.2 Mandatory `--demo` Flag
To prevent accidental execution or confusion with production initialization, the `--demo` flag is required. Running `go run ./cmd/seed` without `--demo` immediately halts with exit code 1:

```text
[ERROR] Missing required flag: --demo
Seeding is restricted to development demo data and requires explicit opt-in.
Usage: go run ./cmd/seed --demo
```

---

## 3. Demonstration Records Inserted

The seed command creates two synthetic facilities and five weekly schedule windows using stable, deterministic UUIDs:

### Facility 1: Badminton Court
- **Stable ID:** `d0000001-0000-4000-8000-000000000001`
- **Slug:** `demo-badminton-court`
- **Name:** `[Demo] Campus Badminton Court`
- **Description:** `Synthetic demonstration court for local testing and timetable preview`
- **Location:** `Demo Sports Hall Wing B`
- **Status:** `active`
- **Schedules:**
  1. `Monday (Day 1)`: `09:00:00` to `12:00:00` | Audience: `student` (`d0000001-0000-4000-8000-000000000011`)
  2. `Wednesday (Day 3)`: `16:00:00` to `18:00:00` | Audience: `faculty` (`d0000001-0000-4000-8000-000000000012`)
  3. `Friday (Day 5)`: `14:00:00` to `16:00:00` | Audience: `women_only` (`d0000001-0000-4000-8000-000000000013`)

### Facility 2: Table Tennis Arena
- **Stable ID:** `d0000002-0000-4000-8000-000000000002`
- **Slug:** `demo-table-tennis`
- **Name:** `[Demo] Table Tennis Arena`
- **Description:** `Synthetic demonstration table tennis arena for local testing`
- **Location:** `Demo Activity Center 1st Floor`
- **Status:** `active`
- **Schedules:**
  1. `Tuesday (Day 2)`: `10:00:00` to `13:00:00` | Audience: `general` (`d0000002-0000-4000-8000-000000000021`)
  2. `Saturday (Day 6)`: `18:00:00` to `21:00:00` | Audience: `student` (`d0000002-0000-4000-8000-000000000022`)

---

## 4. Atomicity, Idempotency, & Administrator Edit Preservation

### 4.1 Single Atomic Transaction
All checks and inserts are executed inside a single PostgreSQL transaction (`tx, err := pool.Begin(ctx)`). If any operation fails or a conflict is detected, `tx.Rollback(ctx)` is triggered, ensuring **zero partial inserts**.

### 4.2 Distinguishing New Fixtures from Existing Records
Before inserting, the seeder queries existing records:
```sql
SELECT id, slug FROM giki_sports.facilities WHERE id = $1 OR slug = $2;
```

1. **No match:** The fixture is new. The facility and all its schedules are inserted.
2. **Exact match (`id == fixture.ID && slug == fixture.Slug`):** The fixture was already seeded.
   - The facility is counted as skipped.
   - Existing facility attributes are **never overwritten**.
   - Schedules are counted as skipped. If an administrator updated schedule times, deleted a schedule, or added custom slots, the seeder **does not recreate the deleted schedule or overwrite the edited one**.
3. **Collision / Conflict (`id` matches but `slug` differs, or `slug` matches but `id` differs):**
   - The seeder aborts with an actionable error (e.g. `fixture conflict: facility with slug "demo-badminton-court" already exists with ID ...`).
   - The transaction rolls back, preventing schedules from accidentally attaching to an unrelated facility.

### 4.3 Summary Output
Every execution reports exact numbers:
- **First Run:**
  ```text
  Seed Summary:
    Facilities: 2 inserted, 0 skipped
    Schedules:  5 inserted, 0 skipped
  ```
- **Repeated Run:**
  ```text
  Seed Summary:
    Facilities: 0 inserted, 2 skipped
    Schedules:  0 inserted, 5 skipped
  ```

---

## 5. Safe Inspection of Seeded Records

To inspect the seeded records in PostgreSQL without modifying data, run:

```powershell
docker exec giki-sports-complex-db-1 psql -U giki_sports_app -d giki_sports_complex -c "
SELECT f.slug, f.name, f.status, s.day_of_week, s.start_time, s.end_time, s.audience
FROM giki_sports.facilities f
LEFT JOIN giki_sports.schedules s ON f.id = s.facility_id
ORDER BY f.name ASC, s.day_of_week ASC, s.start_time ASC;
"
```

Expected output:
```text
         slug         |             name              | status | day_of_week | start_time |  end_time  |  audience  
----------------------+-------------------------------+--------+-------------+------------+------------+------------
 demo-badminton-court | [Demo] Campus Badminton Court | active |           1 | 09:00:00   | 12:00:00   | student
 demo-badminton-court | [Demo] Campus Badminton Court | active |           3 | 16:00:00   | 18:00:00   | faculty
 demo-badminton-court | [Demo] Campus Badminton Court | active |           5 | 14:00:00   | 16:00:00   | women_only
 demo-table-tennis    | [Demo] Table Tennis Arena     | active |           2 | 10:00:00   | 13:00:00   | general
 demo-table-tennis    | [Demo] Table Tennis Arena     | active |           6 | 18:00:00   | 21:00:00   | student
(5 rows)
```

---

## 6. Current Application Reality & Boundaries

> [!NOTE]
> **Existing Endpoints Still Use JSON:**
> The demo records now exist in the local PostgreSQL database, and the Go [facility.Repository](file:///d:/giki%20sports%20complex/backend/internal/facility/repository.go) can read them. However, **existing HTTP endpoints (`GET /api/facilities`, `GET /api/bookings`) continue to serve data from local JSON storage (`backend/data/store.json`).**
> The HTTP API handlers and frontend will be wired to the PostgreSQL repository in the upcoming chunk (Step 4E).
