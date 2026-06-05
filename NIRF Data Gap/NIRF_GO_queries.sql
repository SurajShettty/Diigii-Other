-- =====================================================================
-- NIRF Parameter 3 — Graduation Outcomes (GO): SQL queries
-- DB: collpoll_university @ digiidbcommon...ap-south-1.rds.amazonaws.com
-- Companion to NIRF_GO_data_gap_report.md
--
-- Programme types (programme.programme_type_id -> programme_types.id):
--   1 = Undergraduate   2 = Post-Graduate   3 = PhD
--   4 = Diploma         5 = Certificate
--
-- Validated against live data 2026-06-05. Corrections vs the report:
--   * "Placed" must come from placement_application.status_id IN (1=PLACED, 6=Selected).
--     offer_status_id is NULL for 1283/1285 rows -- DO NOT use it.
--   * placement_student_status tracks REGISTRATION (1=Registered, 2=Not Registered),
--     NOT placement outcome. Use it for the "eligible/registered" denominator only.
--   * ems_examination_student.year spans 1-3 only; there are no final-year (year=duration)
--     exam rows. Filtering by sp.year = p.duration_years collapses to ~0. The GO2 queries
--     therefore scope to UG programmes and let you pick the cohort by AY / passing year.
--   * cgpa_percentage.cgpa and year_percentage.percentage actually hold PERCENTAGES
--     (0-100), but contain bad values >100 (max 220). Filter < 100 to drop garbage.
-- =====================================================================


-- =====================================================================
-- GO1 — Ph.D Degrees Awarded (GPH)
-- Post-Doctoral Fellows: EXTERNAL (HR) -- no table.
-- =====================================================================

-- GO1.1  PhD students by expected graduation year (proxy for degrees awarded).
SELECT sp.expected_year_of_passing AS passing_year,
       COUNT(*)                    AS phd_students
FROM   student_profile sp
JOIN   programme p ON p.programme_id = sp.programme_id
WHERE  p.programme_type_id = 3            -- PhD
GROUP  BY sp.expected_year_of_passing
ORDER  BY passing_year;

-- GO1.2  Validate against transcripts (degrees actually issued).
SELECT COUNT(*) AS phd_transcripts
FROM   ems_examination_student_transcript t
JOIN   student_profile sp ON sp.ukid = t.ukid
JOIN   programme p        ON p.programme_id = sp.programme_id
WHERE  p.programme_type_id = 3;
-- NOTE: confirm the transcript table's student key column name if this errors
-- (run: SELECT * FROM ems_examination_student_transcript LIMIT 1;)


-- =====================================================================
-- GO2 — University Examinations (GUE)   [strongly fillable]
-- Scope = Undergraduate (programme_type_id = 1). Add an AY filter where shown.
-- =====================================================================

-- GO2.1  Students appeared (distinct UG students with an exam record).
SELECT COUNT(DISTINCT es.ukid) AS ug_students_appeared
FROM   ems_examination_student es
JOIN   student_profile sp ON sp.ukid = es.ukid
JOIN   programme p        ON p.programme_id = sp.programme_id
WHERE  p.programme_type_id = 1;

-- GO2.1b  Same, scoped to a specific exam / AY (recommended for final-year cohort).
--         Pick the relevant exam ids from ems_examination (e.g. end-term exams).
SELECT COUNT(DISTINCT es.ukid) AS ug_students_appeared
FROM   ems_examination_student es
JOIN   student_profile sp ON sp.ukid = es.ukid
JOIN   programme p        ON p.programme_id = sp.programme_id
WHERE  p.programme_type_id = 1
  AND  es.exam_id IN (/* :exam_ids */ 14);   -- e.g. 'UG || PG 4th End Semester'

-- GO2.2  Passed in first attempt (no re-exam needed and >= pass mark).
--        Set @pass_pct to the institution's pass percentage (commonly 40 or 50).
SET @pass_pct = 40;
SELECT COUNT(*) AS passed_first_attempt
FROM   ems_examination_student_cgpa_percentage cp
JOIN   student_profile sp ON sp.ukid = cp.student_ukid
JOIN   programme p        ON p.programme_id = sp.programme_id
WHERE  p.programme_type_id = 1
  AND  cp.re_exam_cgpa IS NULL          -- cleared without re-exam
  AND  cp.cgpa >= @pass_pct
  AND  cp.cgpa <= 100;                  -- drop bad data (>100)

-- GO2.3  Pass percentage = passed / appeared (within the same scope).
SELECT
  SUM(cp.re_exam_cgpa IS NULL AND cp.cgpa >= @pass_pct AND cp.cgpa <= 100) AS passed_first_attempt,
  COUNT(*)                                                                  AS total_results,
  ROUND(100 * SUM(cp.re_exam_cgpa IS NULL AND cp.cgpa >= @pass_pct AND cp.cgpa <= 100)
        / NULLIF(COUNT(*),0), 2)                                            AS pass_pct
FROM   ems_examination_student_cgpa_percentage cp
JOIN   student_profile sp ON sp.ukid = cp.student_ukid
JOIN   programme p        ON p.programme_id = sp.programme_id
WHERE  p.programme_type_id = 1
  AND  cp.cgpa <= 100;

-- GO2.4  First Class (>=60%) and Distinction (>=75%) from year-percentage table.
SELECT
  SUM(yp.percentage >= 60) AS first_class_60plus,
  SUM(yp.percentage >= 75) AS distinction_75plus,
  COUNT(*)                 AS total_with_percentage
FROM   ems_examination_student_year_percentage yp
JOIN   student_profile sp ON sp.ukid = yp.student_ukid
JOIN   programme p        ON p.programme_id = sp.programme_id
WHERE  p.programme_type_id = 1
  AND  yp.percentage <= 100              -- drop bad data
  -- AND yp.academic_start_year = 2023   -- optional: filter by AY
;

-- GO2.4b  Same metric from the CGPA-percentage table (larger row count, 122 rows).
SELECT
  SUM(cp.cgpa >= 60) AS first_class_60plus,
  SUM(cp.cgpa >= 75) AS distinction_75plus,
  COUNT(*)           AS total_results
FROM   ems_examination_student_cgpa_percentage cp
JOIN   student_profile sp ON sp.ukid = cp.student_ukid
JOIN   programme p        ON p.programme_id = sp.programme_id
WHERE  p.programme_type_id = 1
  AND  cp.cgpa <= 100;


-- =====================================================================
-- GO3 — Placement, Higher Studies & Entrepreneurship (GPHE)
-- Placement = fillable. Higher Studies / Entrepreneurs = EXTERNAL (alumni survey).
-- "Placed" = placement_application.status_id IN (1 PLACED, 6 Selected).
-- =====================================================================

-- GO3.1  Students placed (distinct).
SELECT COUNT(DISTINCT pa.ukid) AS students_placed
FROM   placement_application pa
WHERE  pa.is_deleted = 0
  AND  pa.status_id IN (1, 6);          -- PLACED, Selected

-- GO3.1b  Students placed per placement cycle / AY (cycle gives the AY window).
SELECT pc.id          AS cycle_id,
       pc.name        AS cycle_name,
       pc.start_date, pc.end_date,
       COUNT(DISTINCT pa.ukid) AS students_placed
FROM   placement_application pa
JOIN   placement_job pj  ON pj.id = pa.job_id
JOIN   placement_cycle pc ON pc.id = pj.placement_cycle
WHERE  pa.is_deleted = 0
  AND  pa.status_id IN (1, 6)
GROUP  BY pc.id, pc.name, pc.start_date, pc.end_date
ORDER  BY pc.start_date;

-- GO3.2  Median salary (LPA). CTC normalised to annual; monthly -> *12; /1e5 for LPA.
SELECT AVG(ctc_lpa) AS median_ctc_lpa
FROM (
  SELECT (CASE WHEN pj.ctc_type='monthly' THEN pj.ctc*12 ELSE pj.ctc END)/100000 AS ctc_lpa,
         ROW_NUMBER() OVER (ORDER BY CASE WHEN pj.ctc_type='monthly' THEN pj.ctc*12 ELSE pj.ctc END) AS rn,
         COUNT(*)     OVER ()                                                     AS cnt
  FROM   placement_application pa
  JOIN   placement_job pj ON pj.id = pa.job_id
  WHERE  pa.is_deleted = 0
    AND  pa.status_id IN (1, 6)
    AND  pj.ctc > 0
) t
WHERE rn IN (FLOOR((cnt+1)/2), FLOOR((cnt+2)/2));   -- median (handles odd/even)

-- GO3.3  Max salary (LPA) across placed offers.
SELECT MAX((CASE WHEN pj.ctc_type='monthly' THEN pj.ctc*12 ELSE pj.ctc END)/100000) AS max_ctc_lpa
FROM   placement_application pa
JOIN   placement_job pj ON pj.id = pa.job_id
WHERE  pa.is_deleted = 0
  AND  pa.status_id IN (1, 6)
  AND  pj.ctc > 0;

-- GO3.4  Placement rate % = placed / eligible(registered).
--        Denominator = students registered for placements (placement_student_status, 1=Registered).
SELECT
  (SELECT COUNT(DISTINCT pa.ukid) FROM placement_application pa
     WHERE pa.is_deleted=0 AND pa.status_id IN (1,6))               AS placed,
  (SELECT COUNT(DISTINCT pss.student_ukid) FROM placement_student_status pss
     WHERE pss.status_id = 1)                                       AS registered,
  ROUND(100 *
    (SELECT COUNT(DISTINCT pa.ukid) FROM placement_application pa
       WHERE pa.is_deleted=0 AND pa.status_id IN (1,6))
    / NULLIF((SELECT COUNT(DISTINCT pss.student_ukid) FROM placement_student_status pss
       WHERE pss.status_id = 1),0), 2)                              AS placement_rate_pct;


-- =====================================================================
-- GO4 — Professional Activities (GPA)   [almost entirely EXTERNAL]
-- GATE / UPSC / CAT / CFA / International exposure: no tables -> request from offices.
-- =====================================================================

-- GO4.1  Internal-only proxy: students who registered for a PhD here, following a UG batch.
--        (Captures only students who continued at THIS institution.)
SELECT COUNT(*) AS phd_registrations_internal
FROM   student_profile sp
JOIN   programme p ON p.programme_id = sp.programme_id
WHERE  p.programme_type_id = 3;          -- PhD enrolments


-- =====================================================================
-- Helper lookups
-- =====================================================================
-- Exams + AY context:        SELECT id, name, term_id, publish_results FROM ems_examination ORDER BY id;
-- Placement cycles (AY):      SELECT id, name, start_date, end_date FROM placement_cycle ORDER BY start_date;
-- Application status codes:   SELECT id, name FROM placement_application_status ORDER BY id;
-- Programme list (UG=1 etc):  SELECT programme_id, programme_name, programme_type_id, duration_years FROM programme WHERE is_deleted=0;