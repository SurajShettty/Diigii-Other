-- =====================================================================
-- NIRF Parameter 4 — Outreach & Inclusivity (OI): SQL queries
-- DB: collpoll_university @ digiidbcommon...ap-south-1.rds.amazonaws.com
-- Companion to NIRF_OI_data_gap_report.md
--
-- Validated against live data 2026-06-05. The report over-rated fillability;
-- actual column population (of 1,675 students / 179 faculty):
--   OI1 Regional Diversity .... NOT FILLABLE. state_of_domicile, domicile,
--        citizenship, nationality, state, city, hometown are ALL empty (0 rows).
--   OI2 Women Diversity ....... FILLABLE. gender enum populated on both profiles.
--        NOTE enum values are lowercase: 'male','female','other'.
--   OI3 SC/ST/OBC/EWS ......... NOT FILLABLE. admission_category & caste are NULL
--        for all 1,675 students. Only `quota` is populated, and it is
--        General/Management/NRI -- NOT the NIRF SC/ST/OBC/EWS categories.
--   OI3 Scholarships .......... EFFECTIVELY EMPTY. student_scholarship = 39 rows,
--        29 deleted, and amount/applicable_amount/approved_amount are all 0.
--   OI3 Fee waiver ............ 2 rows, ₹20,000 total. fee_student_discount empty.
--   OI4 Disabilities .......... EXTERNAL. No disability columns exist.
--
-- The OI1 and OI3-category queries below are written correctly and will start
-- returning data IF/WHEN those columns are populated, but return 0/empty today.
-- =====================================================================


-- =====================================================================
-- OI1 — Regional Diversity (RD)        [NOT FILLABLE TODAY -- fields empty]
-- Set @home_state to the institution's home state once domicile is populated.
-- =====================================================================
SET @home_state = 'Maharashtra';   -- <-- set institution home state

-- OI1.1  Same-state / other-state / international split (by domicile).
SELECT
  SUM(sp.state_of_domicile = @home_state)                                   AS same_state,
  SUM(sp.state_of_domicile <> @home_state AND
      (sp.citizenship IS NULL OR sp.citizenship IN ('India','Indian')))     AS other_state,
  SUM(sp.citizenship IS NOT NULL AND sp.citizenship NOT IN ('India','Indian')) AS international
FROM student_profile sp;

-- OI1.2  Data-completeness check (run before trusting OI1.1).
SELECT COUNT(*) total,
       SUM(state_of_domicile IS NULL OR state_of_domicile='') AS missing_domicile,
       SUM(citizenship       IS NULL OR citizenship='')       AS missing_citizenship
FROM student_profile;
-- TODAY: missing_domicile = 1675/1675. OI1 must be sourced from Admissions until populated.


-- =====================================================================
-- OI2 — Women Diversity (WD)                              [FILLABLE]
-- =====================================================================

-- OI2.1  Students by gender + % women.   (live: 1510 male / 145 female / 20 other)
SELECT
  SUM(gender='female')                                  AS women_students,
  COUNT(*)                                              AS total_students,
  ROUND(100*SUM(gender='female')/NULLIF(COUNT(*),0),2)  AS pct_women_students
FROM student_profile;

-- OI2.1b  Same, scoped to an admission year cohort (for per-AY reporting).
SELECT year_of_joining,
       SUM(gender='female') AS women, COUNT(*) AS total,
       ROUND(100*SUM(gender='female')/NULLIF(COUNT(*),0),2) AS pct_women
FROM student_profile
GROUP BY year_of_joining
ORDER BY year_of_joining;

-- OI2.2  Faculty by gender + % women.    (live: 117 male / 48 female / 14 null)
SELECT
  SUM(gender='female')                                  AS women_faculty,
  COUNT(*)                                              AS total_faculty,
  ROUND(100*SUM(gender='female')/NULLIF(COUNT(*),0),2)  AS pct_women_faculty
FROM faculty_profile;

-- OI2.2b  "Regular" faculty only -- inspect designations first, then filter.
--         SELECT designation, COUNT(*) FROM faculty_profile GROUP BY designation;
--         Exclude guest/visiting/adjunct once you confirm the label text:
SELECT
  SUM(gender='female') AS women_regular_faculty,
  COUNT(*)             AS total_regular_faculty
FROM faculty_profile
WHERE COALESCE(designation,'') NOT REGEXP 'guest|visit|adjunct|contract';


-- =====================================================================
-- OI3 — Economically & Socially Challenged Students (ESCS)
-- SC/ST/OBC/EWS: NOT FILLABLE today (admission_category & caste all NULL).
-- =====================================================================

-- OI3.1  SC / ST / OBC / EWS counts (CORRECT query; returns 0 until populated).
SELECT
  SUM(UPPER(admission_category)='SC')  AS sc_students,
  SUM(UPPER(admission_category)='ST')  AS st_students,
  SUM(UPPER(admission_category)='OBC') AS obc_students,
  SUM(UPPER(admission_category)='EWS') AS ews_students,
  SUM(admission_category IS NULL OR admission_category='') AS uncategorised
FROM student_profile;
-- TODAY uncategorised = 1675/1675. Source SC/ST/OBC/EWS from Admissions.

-- OI3.1b  Only populated categorisation = quota (NOT NIRF categories, for reference).
--         live: General 1654, Management 19, NRI 2
SELECT q.name AS quota, COUNT(*) AS students
FROM student_profile sp
LEFT JOIN quota q ON q.id = sp.quota_id
GROUP BY q.name
ORDER BY students DESC;

-- OI3.2  EWS by income fallback (only if income gets populated; currently all NULL).
SELECT COUNT(*) AS ews_by_income
FROM student_profile
WHERE COALESCE(parents_income, father_annual_income) < 800000
  AND COALESCE(parents_income, father_annual_income) IS NOT NULL;

-- OI3.3  Scholarship recipients (distinct students with an approved scholarship).
--        student_scholarship has no student id -- join via student_fee.ukid.
--        TODAY: 39 rows, 29 deleted, all amounts 0 -> returns 0. Verify with Finance.
SELECT COUNT(DISTINCT sf.ukid) AS scholarship_recipients
FROM student_scholarship ss
JOIN student_fee sf ON sf.id = ss.student_fee_id
WHERE ss.is_deleted = 0
  AND ss.approved_amount > 0;     -- if all 0, try ss.applicable_amount / ss.amount

-- OI3.4  Fee waiver / concession granted (₹ Lakhs).
--        live: student_fee_waiver = 2 rows, ₹20,000 total (0.20 L); fee_student_discount empty.
SELECT
  ROUND(COALESCE((SELECT SUM(waiver_amount) FROM student_fee_waiver),0)/100000, 2) AS waiver_lakhs,
  ROUND(COALESCE((SELECT SUM(amount)        FROM fee_student_discount),0)/100000, 2) AS discount_lakhs;


-- =====================================================================
-- OI4 — Facilities for Persons with Disabilities (FPHD)   [EXTERNAL]
-- No disability columns/tables exist. Source from Admissions / Estate / Library.
-- =====================================================================
-- (no query)


-- =====================================================================
-- Helper lookups
-- =====================================================================
-- Faculty designations:  SELECT designation, COUNT(*) FROM faculty_profile GROUP BY designation;
-- Quota values:          SELECT id, name FROM quota;
-- Column population scan: SELECT COUNT(*) total,
--                                SUM(<col> IS NOT NULL AND <col><>'') AS populated
--                         FROM student_profile;
