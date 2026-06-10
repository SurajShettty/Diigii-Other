-- =====================================================================
-- NIRF — 5 minimum DAGs, ACADEMIC-YEAR-WISE (tidy: one row per AY)
-- DB: collpoll_university @ digiidbcommon...ap-south-1.rds.amazonaws.com
--
-- One self-contained query per DAG (no session vars; params via a CTE).
-- AY spine = the LAST 3 academic years actually present in each source.
-- AY label = CONCAT(start,'-',RIGHT(start+1,2))  e.g. 2023 -> '2023-24'.
-- AY boundary for date columns = July->June: ay = YEAR(d) - (MONTH(d) < 7).
--
-- SNAPSHOT-ONLY metrics (no historical AY in the DB) are emitted ONLY in
-- the latest AY row, suffixed _current, NULL in earlier rows:
--   * faculty count / FSR / women-faculty  (faculty.year_of_joining 0/179)
--   * all infrastructure                    (no date column at all)
--   * UG appeared / pass%                   (cgpa_percentage has no AY col)
-- These are flagged inline so they are not read as a historical trend.
--
-- CAVEAT (live): student_profile.year_of_joining contains FUTURE intake years
-- (2025, 2026), so "last 3" for DAG1/DAG2 resolves to 2024-25 / 2025-26 /
-- 2026-27 and the snapshot lands on 2026-27. To report only completed AYs,
-- add  WHERE year_of_joining <= 2025  to the coh/spine CTEs.
-- Validated against live data 2026-06-10. All 5 queries run; values below.
--   DAG1 enrolled ~1,672 (2024-25); women-admitted 28.9% / 6.7% / 20%
--   DAG2 85 classrooms / 3,600 seats / 14 labs (snapshot @ 2026-27)
--   DAG3 first-class 2 (2022-23) & 9 (2023-24); pass% 47.06 (all-prog snapshot)
--   DAG4 placed 6 / 46 / 0 ; rate 60% / 49% ; median 6.0 / 4.05 LPA
--   DAG5 (test data) 3 proj / 0.30 L ; 2 proj / 20 L
-- =====================================================================


-- #####################################################################
-- DAG 1 / people_metrics  (AY = student admission cohort, last 3)
-- AY-wise: enrolled, admitted, women.  Latest-AY-only: faculty/FSR/women-fac.
-- #####################################################################
WITH coh AS (
  SELECT year_of_joining AS ay,
         COUNT(*)               AS students_admitted,
         SUM(gender='female')   AS women_admitted
  FROM   student_profile
  WHERE  year_of_joining IS NOT NULL
  GROUP  BY year_of_joining
),
spine AS (SELECT ay FROM coh ORDER BY ay DESC LIMIT 3),
waiv AS (
  SELECT YEAR(created_timestamp) - (MONTH(created_timestamp) < 7) AS ay,
         SUM(waiver_amount) AS amt
  FROM   student_fee_waiver
  GROUP  BY ay
)
SELECT
  CONCAT(s.ay,'-',RIGHT(s.ay+1,2)) AS academic_year,
  -- enrolled DURING this AY (span: joined on/before AY end, not yet passed at AY start)
  (SELECT COUNT(*) FROM student_profile sp
     WHERE sp.year_of_joining <= s.ay+1
       AND (sp.expected_year_of_passing IS NULL OR sp.expected_year_of_passing >= s.ay)) AS students_enrolled,
  c.students_admitted,
  c.women_admitted,
  ROUND(100*c.women_admitted/NULLIF(c.students_admitted,0),2)            AS pct_women_admitted,
  ROUND(COALESCE(w.amt,0)/100000,2)                                      AS waiver_lakhs,
  -- ---- snapshot-only: latest AY row only ----
  CASE WHEN s.ay=(SELECT MAX(ay) FROM spine) THEN (SELECT COUNT(*) FROM faculty_profile) END AS faculty_current,
  CASE WHEN s.ay=(SELECT MAX(ay) FROM spine) THEN
       ROUND((SELECT COUNT(*) FROM student_profile)/NULLIF((SELECT COUNT(*) FROM faculty_profile),0),2) END AS fsr_current,
  CASE WHEN s.ay=(SELECT MAX(ay) FROM spine) THEN (SELECT SUM(gender='female') FROM faculty_profile) END AS women_faculty_current,
  CASE WHEN s.ay=(SELECT MAX(ay) FROM spine) THEN
       ROUND(100*(SELECT SUM(gender='female') FROM faculty_profile)/NULLIF((SELECT COUNT(*) FROM faculty_profile),0),2) END AS pct_women_faculty_current
FROM   spine s
LEFT   JOIN coh  c ON c.ay = s.ay
LEFT   JOIN waiv w ON w.ay = s.ay
ORDER  BY s.ay;


-- #####################################################################
-- DAG 2 / infrastructure_metrics  (no date dimension -> single snapshot row,
-- labelled with the latest student AY per the snapshot rule)
-- #####################################################################
WITH spine AS (
  SELECT MAX(year_of_joining) AS ay FROM student_profile WHERE year_of_joining IS NOT NULL
)
SELECT
  CONCAT(ay,'-',RIGHT(ay+1,2)) AS academic_year,
  (SELECT COUNT(*)                  FROM infrastructure_master WHERE type_id=11 AND archived=0) AS classrooms_current,
  (SELECT COALESCE(SUM(capacity),0) FROM infrastructure_master WHERE type_id=11 AND archived=0) AS classroom_seats_current,
  (SELECT COUNT(*)                  FROM infrastructure_master WHERE type_id=7  AND archived=0) AS laboratories_current,
  (SELECT COALESCE(SUM(capacity),0) FROM infrastructure_master WHERE type_id=7  AND archived=0) AS lab_seats_current,
  (SELECT COUNT(*)                  FROM infrastructure_master WHERE type_id=4  AND archived=0) AS hostel_beds_current,
  (SELECT COALESCE(SUM(capacity),0) FROM infrastructure_master WHERE type_id=2  AND archived=0) AS hostel_room_capacity_current,
  (SELECT COALESCE(SUM(capacity),0) FROM infrastructure_master WHERE type_id=1  AND archived=0) AS hostel_building_capacity_current
FROM spine;


-- #####################################################################
-- DAG 3 / examination_outcomes  (AY = ems_examination_student_year_percentage
-- .academic_start_year, last 3 = the only true exam AY column)
-- AY-wise: first-class / distinction.  Latest-AY-only: appeared / pass% (those
-- tables carry no academic-year column).
-- #####################################################################
WITH param AS (SELECT 40 AS pass_pct),     -- institution pass mark (40 or 50)
fc AS (
  SELECT yp.academic_start_year AS ay,
         SUM(yp.percentage>=60) AS first_class_60plus,
         SUM(yp.percentage>=75) AS distinction_75plus,
         COUNT(*)               AS results_with_pct
  FROM   ems_examination_student_year_percentage yp
  JOIN   student_profile sp ON sp.ukid = yp.student_ukid
  JOIN   programme p        ON p.programme_id = sp.programme_id
  WHERE  p.programme_type_id = 1 AND yp.percentage <= 100
    AND  yp.academic_start_year IS NOT NULL
  GROUP  BY yp.academic_start_year
),
spine AS (SELECT ay FROM fc ORDER BY ay DESC LIMIT 3)
SELECT
  CONCAT(s.ay,'-',RIGHT(s.ay+1,2)) AS academic_year,
  fc.first_class_60plus,
  fc.distinction_75plus,
  fc.results_with_pct,
  -- ---- snapshot-only (no AY column on source tables): latest AY row only ----
  CASE WHEN s.ay=(SELECT MAX(ay) FROM spine) THEN
    (SELECT COUNT(DISTINCT es.ukid) FROM ems_examination_student es
       JOIN student_profile sp ON sp.ukid=es.ukid
       JOIN programme p ON p.programme_id=sp.programme_id
       WHERE p.programme_type_id=1) END AS ug_appeared_current,
  -- NOTE: ems_examination_student_cgpa_percentage holds ONLY PG results today
  --       (0 UG rows), so first-attempt pass% is institution-wide (all
  --       programmes), NOT UG-scoped. live: 47.06% (32/68).
  CASE WHEN s.ay=(SELECT MAX(ay) FROM spine) THEN
    (SELECT SUM(cp.re_exam_cgpa IS NULL AND cp.cgpa>=(SELECT pass_pct FROM param) AND cp.cgpa<=100)
       FROM ems_examination_student_cgpa_percentage cp WHERE cp.cgpa<=100) END AS passed_first_attempt_current,
  CASE WHEN s.ay=(SELECT MAX(ay) FROM spine) THEN
    (SELECT ROUND(100*SUM(cp.re_exam_cgpa IS NULL AND cp.cgpa>=(SELECT pass_pct FROM param) AND cp.cgpa<=100)/NULLIF(COUNT(*),0),2)
       FROM ems_examination_student_cgpa_percentage cp WHERE cp.cgpa<=100) END AS pass_pct_current
FROM   spine s
LEFT   JOIN fc ON fc.ay = s.ay
ORDER  BY s.ay;


-- #####################################################################
-- DAG 4 / placement_metrics  (AY = placement_cycle.start_date, last 3)
-- AY-wise: placed, median/max CTC.  registered+rate use created-date AY (proxy).
-- "Placed" = placement_application.status_id IN (1 PLACED, 6 Selected).
-- #####################################################################
WITH base AS (
  SELECT YEAR(pc.start_date) - (MONTH(pc.start_date) < 7) AS ay,
         pa.ukid, pa.status_id,
         (CASE WHEN pj.ctc_type='monthly' THEN pj.ctc*12 ELSE pj.ctc END)/100000 AS ctc_lpa
  FROM   placement_application pa
  JOIN   placement_job   pj ON pj.id = pa.job_id
  JOIN   placement_cycle pc ON pc.id = pj.placement_cycle
  WHERE  pa.is_deleted = 0
),
placed AS (
  SELECT ay,
         COUNT(DISTINCT CASE WHEN status_id IN (1,6) THEN ukid END)                  AS placed,
         MAX(CASE WHEN status_id IN (1,6) AND ctc_lpa>0 THEN ctc_lpa END)            AS max_ctc_lpa
  FROM   base GROUP BY ay
),
med AS (   -- median CTC among placed offers, per AY
  SELECT ay, AVG(ctc_lpa) AS median_ctc_lpa FROM (
    SELECT ay, ctc_lpa,
           ROW_NUMBER() OVER (PARTITION BY ay ORDER BY ctc_lpa) AS rn,
           COUNT(*)     OVER (PARTITION BY ay)                  AS cnt
    FROM   base WHERE status_id IN (1,6) AND ctc_lpa > 0
  ) t WHERE rn IN (FLOOR((cnt+1)/2), FLOOR((cnt+2)/2)) GROUP BY ay
),
reg AS (   -- registered (proxy: created-date AY; placement_student_status has no cycle FK)
  SELECT YEAR(created_timestamp) - (MONTH(created_timestamp) < 7) AS ay,
         COUNT(DISTINCT student_ukid) AS registered
  FROM   placement_student_status WHERE status_id = 1 GROUP BY ay
),
spine AS (SELECT ay FROM placed ORDER BY ay DESC LIMIT 3)
SELECT
  CONCAT(s.ay,'-',RIGHT(s.ay+1,2)) AS academic_year,
  p.placed,
  r.registered,
  ROUND(100*p.placed/NULLIF(r.registered,0),2) AS placement_rate_pct_proxy,
  ROUND(m.median_ctc_lpa,2)                     AS median_ctc_lpa,
  ROUND(p.max_ctc_lpa,2)                        AS max_ctc_lpa
FROM   spine s
LEFT   JOIN placed p ON p.ay = s.ay
LEFT   JOIN med    m ON m.ay = s.ay
LEFT   JOIN reg    r ON r.ay = s.ay
ORDER  BY s.ay;


-- #####################################################################
-- DAG 5 / funding_projects  [DORMANT — test data]  (AY = grant_start_date)
-- #####################################################################
WITH g AS (
  SELECT YEAR(s.grant_start_date) - (MONTH(s.grant_start_date) < 7) AS ay,
         COUNT(DISTINCT p.id)         AS funded_projects,
         SUM(DISTINCT s.grant_amount) AS grant_amt
  FROM   project p
  JOIN   project_funding_agency_scheme s ON s.id = p.project_funding_agency_scheme_id
  WHERE  p.is_draft = 0 AND s.grant_start_date IS NOT NULL
  GROUP  BY ay
),
spine AS (SELECT ay FROM g ORDER BY ay DESC LIMIT 3)
SELECT
  CONCAT(s.ay,'-',RIGHT(s.ay+1,2)) AS academic_year,
  g.funded_projects,
  ROUND(g.grant_amt/100000,2)      AS funding_lakhs
FROM   spine s
LEFT   JOIN g ON g.ay = s.ay
ORDER  BY s.ay;
