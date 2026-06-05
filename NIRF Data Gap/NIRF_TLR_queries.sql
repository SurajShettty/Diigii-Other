-- =====================================================================
-- NIRF Parameter 1 — Teaching, Learning & Resources (TLR): SQL queries
-- DB: collpoll_university @ digiidbcommon...ap-south-1.rds.amazonaws.com
-- Companion to NIRF_TLR_data_gap_report.md
--
-- Validated against live data 2026-06-05. Population reality:
--   FACULTY (179 rows): qualification, experience, year_of_joining are ALL NULL.
--     -> "Faculty with Ph.D", "Experience > 5yr", and AY-historical faculty
--        snapshots are NOT FILLABLE. Only the raw head-count is usable. GATE/NET
--        is external. No qualification master table exists.
--   STUDENTS (1,675): year_of_joining populated for all; expected_year_of_passing
--     for 1,298; student_status_id set for only 4 (treat NULL as active).
--   INFRASTRUCTURE (990 rows, 986 active, 962 with capacity):
--     Classroom (type 11): 85 rooms, 3,600 seats   -> FILLABLE
--     Laboratory (type 7): 14 rooms, 318 seats      -> count/seats fillable;
--        lab AREA (sq.m) is NOT in the DB (no area column/attribute) -> external.
--     Hostel beds (type 4): 622; Hostel rooms (type 2): 224/657 cap.
--     Smart/ICT classroom: NOT FILLABLE. infrastructure_attributes_master only
--        has AC / NON-AC / Fan / Light / Mirror -- no smart-board/ICT/projector.
--     Library/e-journals/bandwidth: external.
--   TLR2 Financial Resources: ENTIRELY EXTERNAL (Finance ERP). No budget tables.
-- =====================================================================


-- =====================================================================
-- TLR1 — Faculty-Student Ratio with Ph.D (FSR)
-- =====================================================================

-- TLR1.1  Total full-time faculty (head-count).   live: 179
--         CAVEAT: no active/terminated flag, no year_of_joining -> cannot make
--         per-AY historical snapshots from CollPoll. Confirm roster with HR.
SELECT COUNT(*) AS total_faculty FROM faculty_profile;

-- TLR1.2  Total students enrolled (current).   live: 1,675
SELECT COUNT(*) AS total_students FROM student_profile;

-- TLR1.3  Students enrolled DURING a given AY (set @ay_start / @ay_end years).
--         Enrolled = joined on/before AY end AND not yet passed out at AY start.
SET @ay_start = 2023;   -- e.g. AY 2023-24
SET @ay_end   = 2024;
SELECT COUNT(*) AS students_enrolled_in_ay
FROM   student_profile
WHERE  year_of_joining <= @ay_end
  AND  (expected_year_of_passing IS NULL OR expected_year_of_passing >= @ay_start);

-- TLR1.4  Faculty-Student Ratio (FSR) = students / faculty.
SELECT (SELECT COUNT(*) FROM student_profile) AS students,
       (SELECT COUNT(*) FROM faculty_profile) AS faculty,
       ROUND((SELECT COUNT(*) FROM student_profile)
             / NULLIF((SELECT COUNT(*) FROM faculty_profile),0), 2) AS fsr;

-- TLR1.5  Faculty with Ph.D  -- NOT FILLABLE (qualification NULL for all 179).
--         Query is correct for when HR populates faculty_profile.qualification
--         (FK to a qualification master that must first be created/identified).
SELECT COUNT(*) AS phd_faculty
FROM   faculty_profile
WHERE  qualification IS NOT NULL;   -- returns 0 today; source Ph.D status from HR

-- TLR1.6  Faculty with experience > 5yr -- NOT FILLABLE (experience NULL for all).
SELECT COUNT(*) AS faculty_exp_gt_5
FROM   faculty_profile
WHERE  experience > 5;              -- returns 0 today; source from HR

-- Qualifying Exam (GATE/NET) qualified faculty: EXTERNAL (HR). No column.


-- =====================================================================
-- TLR2 — Financial Resources & Utilisation (FRU)   [ENTIRELY EXTERNAL]
-- Budget / Capex / Opex / Research funding / Utilisation: Finance ERP.
-- "Budget per student" denominator (student count) comes from TLR1.2.
-- (no fillable query -- see NIRF_RP_queries.sql RP4 for the sparse project module)
-- =====================================================================


-- =====================================================================
-- TLR3 — Quality Teaching & Learning Infrastructure
-- =====================================================================

-- TLR3.1  Classroom seating capacity.   live: 85 rooms, 3,600 seats
SELECT COUNT(*)             AS classrooms,
       COALESCE(SUM(capacity),0) AS total_seating_capacity
FROM   infrastructure_master
WHERE  type_id = 11            -- Classroom
  AND  archived = 0;

-- TLR3.2  Laboratory count + seating (lab AREA in sq.m is NOT in DB -> external).
SELECT COUNT(*)             AS laboratories,
       COALESCE(SUM(capacity),0) AS total_lab_seats
FROM   infrastructure_master
WHERE  type_id = 7             -- Laboratory
  AND  archived = 0;

-- TLR3.3  Hostel capacity. Best signal = Hostel Bed rows.   live: 622 beds
SELECT
  (SELECT COUNT(*) FROM infrastructure_master WHERE type_id=4 AND archived=0)            AS hostel_beds,
  (SELECT COALESCE(SUM(capacity),0) FROM infrastructure_master WHERE type_id=2 AND archived=0) AS hostel_room_capacity,
  (SELECT COALESCE(SUM(capacity),0) FROM infrastructure_master WHERE type_id=1 AND archived=0) AS hostel_building_capacity;

-- TLR3.4  Full capacity breakdown by infrastructure type (overview / sanity).
SELECT t.type,
       COUNT(m.id)                AS rooms,
       COALESCE(SUM(m.capacity),0) AS total_capacity
FROM   infrastructure_type t
LEFT   JOIN infrastructure_master m ON m.type_id = t.id AND m.archived = 0
GROUP  BY t.id, t.type
HAVING rooms > 0
ORDER  BY total_capacity DESC;

-- TLR3.5  Smart/ICT classrooms -- NOT FILLABLE. Only AC/Fan/Light/Mirror attributes
--         exist. This query shows classrooms tagged 'AC' as the closest proxy;
--         source true ICT/smart-board counts from IT/Admin.
SELECT am.name AS attribute, COUNT(*) AS classrooms_with_attr
FROM   infrastructure_master m
JOIN   infrastructure_attributes ia ON ia.infrastructure_id = m.id
JOIN   infrastructure_attributes_master am ON am.id = ia.attribute_id
WHERE  m.type_id = 11 AND m.archived = 0
GROUP  BY am.name;

-- Library volumes / e-journals / databases: EXTERNAL (LMS). Library type rows
--   hold seating capacity (~70), not book counts.
-- Internet bandwidth (Mbps): EXTERNAL (IT/Admin). No schema.


-- =====================================================================
-- Helper lookups
-- =====================================================================
-- Infra types:        SELECT id, type, identifier FROM infrastructure_type;
-- Infra attributes:   SELECT id, name, group_id FROM infrastructure_attributes_master;
-- Faculty population:  SELECT COUNT(*) total,
--                            SUM(qualification IS NOT NULL) has_qual,
--                            SUM(experience IS NOT NULL)    has_exp
--                      FROM faculty_profile;
