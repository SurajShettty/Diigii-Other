-- =====================================================================
-- NIRF — 5 minimum DAGs, ACADEMIC-YEAR-WISE (tidy: one row per AY)
-- DB: collpoll_university @ digiidbcommon...ap-south-1.rds.amazonaws.com
--
-- One self-contained query per DAG (no session vars; params via a CTE).
-- AY spine = the LAST 3 academic years actually present in each source.
-- AY label = CONCAT(start,'-',RIGHT(start+1,2))  e.g. 2023 -> '2023-24'.
-- AY boundary for date columns = July->June: ay = YEAR(d) - (MONTH(d) < 7).
--
-- ALL metrics are AY-wise. Where a table has no natural academic-year column,
-- AY is derived from created_timestamp, CUMULATIVE (= stock on/before that AY):
--   * faculty count / FSR / women-faculty -> faculty_profile.created_timestamp
--   * infrastructure capacity             -> infrastructure_master.created_timestamp
--   * exams (appeared / pass / class)      -> exam -> term.acad_year_start
-- (faculty_profile has no year_of_joining/termination flag; infra has no other
--  date. Switch the cumulative '<= s.ay' to '= s.ay' for per-AY additions.)
--
-- CAVEAT (live): student_profile.year_of_joining contains FUTURE intake years
-- (2025, 2026), so DAG1's "last 3" resolves to 2024-25 / 2025-26 / 2026-27.
-- To report only completed AYs, add  WHERE year_of_joining <= 2025  to coh.
-- Validated against live data 2026-06-10. All 5 queries run; values below.
--   DAG1 2024-25: enrolled 1,672, faculty 78, FSR 21.4 ; 2025-26 faculty 179, FSR 9.4
--   DAG2 2024-25: 72 classrooms/3,400 seats/9 labs -> 2025-26: 85/3,600/14
--   DAG3 2024-25: 146 appeared, 68 results, 47.06% pass, 21 first-class, 9 distinction
--   DAG4 placed 6 / 46 / 0 ; rate 60% / 49% ; median 6.0 / 4.05 LPA
--   DAG5 (test data) 3 proj / 0.30 L ; 2 proj / 20 L
-- =====================================================================


-- #####################################################################
-- DAG 1 / people_metrics  (AY = student admission cohort, last 3)
-- AY-wise: enrolled, admitted, women, + faculty/FSR/women-faculty
-- (faculty cumulative by faculty_profile.created_timestamp AY).
-- #####################################################################
WITH coh AS (
  SELECT sp.year_of_joining AS ay,
         COUNT(*)                 AS students_admitted,
         SUM(sp.gender='female')  AS women_admitted
  FROM   student_profile sp
  WHERE  sp.year_of_joining IS NOT NULL
  GROUP  BY sp.year_of_joining
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
  -- faculty roster = CUMULATIVE by created_timestamp AY (faculty_profile has no
  -- year_of_joining and no termination flag, so this counts faculty whose record
  -- existed on/before each AY). Switch '<= s.ay' to '= s.ay' for per-AY additions.
  (SELECT COUNT(*) FROM faculty_profile f
     WHERE YEAR(f.created_timestamp)-(MONTH(f.created_timestamp)<7) <= s.ay) AS faculty_headcount,
  ROUND(
     (SELECT COUNT(*) FROM student_profile sp
        WHERE sp.year_of_joining <= s.ay+1
          AND (sp.expected_year_of_passing IS NULL OR sp.expected_year_of_passing >= s.ay))
     / NULLIF((SELECT COUNT(*) FROM faculty_profile f
        WHERE YEAR(f.created_timestamp)-(MONTH(f.created_timestamp)<7) <= s.ay),0), 2) AS fsr,
  (SELECT SUM(f.gender='female') FROM faculty_profile f
     WHERE YEAR(f.created_timestamp)-(MONTH(f.created_timestamp)<7) <= s.ay) AS women_faculty,
  ROUND(100*(SELECT SUM(f.gender='female') FROM faculty_profile f
        WHERE YEAR(f.created_timestamp)-(MONTH(f.created_timestamp)<7) <= s.ay)
     / NULLIF((SELECT COUNT(*) FROM faculty_profile f
        WHERE YEAR(f.created_timestamp)-(MONTH(f.created_timestamp)<7) <= s.ay),0), 2) AS pct_women_faculty
FROM   spine s
LEFT   JOIN coh  c ON c.ay = s.ay
LEFT   JOIN waiv w ON w.ay = s.ay
ORDER  BY s.ay;


-- #####################################################################
-- DAG 2 / infrastructure_metrics  (AY = infrastructure_master.created_timestamp,
-- last 3).  Capacity is CUMULATIVE (stock created on/before each AY) -- NIRF
-- wants total available infrastructure, not per-AY additions.
-- NOTE live: infra was bulk-loaded in AY 2024-25 (955 rows) + 31 in 2025-26,
-- so only 2 AYs exist and growth is small. Switch '<= s.ay' to '= s.ay' for adds.
-- #####################################################################
WITH infra AS (
  SELECT type_id, capacity,
         YEAR(created_timestamp) - (MONTH(created_timestamp) < 7) AS ay
  FROM   infrastructure_master
  WHERE  archived = 0 AND created_timestamp IS NOT NULL
),
spine AS (SELECT DISTINCT ay FROM infra ORDER BY ay DESC LIMIT 3)
SELECT
  CONCAT(s.ay,'-',RIGHT(s.ay+1,2)) AS academic_year,
  (SELECT COUNT(*)                  FROM infra i WHERE i.type_id=11 AND i.ay<=s.ay) AS classrooms,
  (SELECT COALESCE(SUM(capacity),0) FROM infra i WHERE i.type_id=11 AND i.ay<=s.ay) AS classroom_seats,
  (SELECT COUNT(*)                  FROM infra i WHERE i.type_id=7  AND i.ay<=s.ay) AS laboratories,
  (SELECT COALESCE(SUM(capacity),0) FROM infra i WHERE i.type_id=7  AND i.ay<=s.ay) AS lab_seats,
  (SELECT COUNT(*)                  FROM infra i WHERE i.type_id=4  AND i.ay<=s.ay) AS hostel_beds,
  (SELECT COALESCE(SUM(capacity),0) FROM infra i WHERE i.type_id=2  AND i.ay<=s.ay) AS hostel_room_capacity,
  (SELECT COALESCE(SUM(capacity),0) FROM infra i WHERE i.type_id=1  AND i.ay<=s.ay) AS hostel_building_capacity
FROM   spine s
ORDER  BY s.ay;


-- #####################################################################
-- DAG 3 / examination_outcomes  (AY = term.acad_year_start, last 3)
-- Base tables (NOT the 39-row year_percentage summary):
--   appeared          = ems_examination_student      (296 rows, who sat exams)
--   results / pass    = ems_examination_student_cgpa_percentage (per exam result)
-- AY is resolved properly via  exam -> ems_examination.term_id -> term.acad_year_start
-- so EVERY metric is genuinely AY-wise (no snapshot-only columns).
-- pass% is institution-wide (all programmes); cgpa_percentage is PG-dominated and
-- a UG filter collapses it to ~0. cgpa here holds PERCENTAGE (0-100); drop >100 garbage.
-- #####################################################################
WITH param AS (SELECT 40 AS pass_pct),     -- institution pass mark (40 or 50)
exam_ay AS (                                -- exam -> academic-year start
  SELECT e.id AS exam_id, t.acad_year_start AS ay
  FROM   ems_examination e
  JOIN   term t ON t.id = e.term_id
  WHERE  t.acad_year_start IS NOT NULL
),
appeared AS (                              -- students who sat exams, per AY
  SELECT x.ay, COUNT(DISTINCT es.ukid) AS appeared
  FROM   ems_examination_student es
  JOIN   exam_ay x ON x.exam_id = es.exam_id
  GROUP  BY x.ay
),
res AS (                                    -- published results + pass quality, per AY
  SELECT x.ay,
         SUM(cp.cgpa<=100)                                                                AS results,
         SUM(cp.re_exam_cgpa IS NULL AND cp.cgpa>=(SELECT pass_pct FROM param) AND cp.cgpa<=100) AS passed_first_attempt,
         SUM(cp.cgpa>=60 AND cp.cgpa<=100)                                                AS first_class_60plus,
         SUM(cp.cgpa>=75 AND cp.cgpa<=100)                                                AS distinction_75plus
  FROM   ems_examination_student_cgpa_percentage cp
  JOIN   exam_ay x ON x.exam_id = cp.exam_id
  GROUP  BY x.ay
),
spine AS (SELECT ay FROM appeared ORDER BY ay DESC LIMIT 3)
SELECT
  CONCAT(s.ay,'-',RIGHT(s.ay+1,2)) AS academic_year,
  a.appeared,
  r.results,
  r.passed_first_attempt,
  ROUND(100*r.passed_first_attempt/NULLIF(r.results,0),2) AS pass_pct,
  r.first_class_60plus,
  r.distinction_75plus
FROM   spine s
LEFT   JOIN appeared a ON a.ay = s.ay
LEFT   JOIN res      r ON r.ay = s.ay
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
