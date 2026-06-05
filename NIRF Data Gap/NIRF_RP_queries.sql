-- =====================================================================
-- NIRF Parameter 2 — Research & Professional Practice (RP): SQL queries
-- DB: collpoll_university @ digiidbcommon...ap-south-1.rds.amazonaws.com
-- Companion to NIRF_RP_data_gap_report.md
--
-- Validated against live data 2026-06-05.
--   RP1 Research Publications (PU) ... EXTERNAL (Scopus / WoS APIs). No pub data.
--   RP2 Quality of Publications (QP). EXTERNAL (Scopus/WoS: h-index, citations).
--   RP3 IPR & Patents .............. EXTERNAL. No patent/ipr/license tables exist.
--   RP4 Projects & Funding (FPPP) .. SCHEMA EXISTS but data is test-only & sparse:
--        project = 5 rows (all test data, e.g. titles "hkjhklh"),
--        project_funding_agency = 3, project_funding_agency_scheme = 3,
--        faculty_research = 0 rows, faculty_profile = 179.
--   Only RP1's denominator (faculty count) and the RP4 module touch CollPoll.
--
-- Report correction: agency_type enum is PRIVATE / GOVERNMENT / SEMI_PRIVATE
-- (NOT 'Industry'). There is a separate region enum INDIAN / INTERNATIONAL.
-- Sponsored-vs-consultancy is NOT modelled -- project_type is thematic only
-- (Science & Technology / AI & ML / Nano Technology), so "consultancy" cannot
-- be filtered from the schema. Treat GOVERNMENT agency_type as "sponsored (Govt)".
-- =====================================================================


-- =====================================================================
-- RP1 — Research Publications (PU)        [EXTERNAL -- Scopus / WoS]
-- Only the per-faculty denominator comes from CollPoll.
-- =====================================================================

-- RP1.1  Total faculty (denominator for "Publications per Faculty"). live: 179
SELECT COUNT(*) AS total_faculty FROM faculty_profile;

-- RP1.2  Self-reported publications in CollPoll (unused module; live: 0 rows).
--        For NIRF use Scopus/WoS, not this table.
SELECT year, COUNT(*) AS publications
FROM   faculty_research
GROUP  BY year
ORDER  BY year;
-- Scopus/WoS counts, h-index, citations, HCP (RP1/RP2) are sourced externally.


-- =====================================================================
-- RP2 — Quality of Publications (QP)      [EXTERNAL -- Scopus / WoS]
-- h-index, citations, highly-cited papers, avg citation/paper. No DB source.
-- (no query)
-- =====================================================================


-- =====================================================================
-- RP3 — IPR & Patents                     [EXTERNAL -- IPR Cell / IPO India]
-- No patent / ipr / intellectual / license tables exist. No DB source.
-- (no query)
-- =====================================================================


-- =====================================================================
-- RP4 — Footprint of Projects & Professional Practice (FPPP)
-- Schema exists; data is test-only/sparse. Queries are correct & ready for
-- when the module is populated. Currency assumed INR; /1e5 -> Lakhs.
-- =====================================================================

-- RP4.1  Project counts by funding-agency type and region.
--        ("Sponsored Govt" = agency_type GOVERNMENT.)
SELECT a.agency_type,
       a.region,
       COUNT(*) AS projects
FROM   project p
JOIN   project_funding_agency_scheme s ON s.id = p.project_funding_agency_scheme_id
JOIN   project_funding_agency a        ON a.id = s.project_funding_agency_id
WHERE  p.is_draft = 0
GROUP  BY a.agency_type, a.region
ORDER  BY projects DESC;

-- RP4.2  Sponsored research projects (Government-funded), count + students/staff.
SELECT COUNT(*) AS govt_sponsored_projects
FROM   project p
JOIN   project_funding_agency_scheme s ON s.id = p.project_funding_agency_scheme_id
JOIN   project_funding_agency a        ON a.id = s.project_funding_agency_id
WHERE  p.is_draft = 0
  AND  a.agency_type = 'GOVERNMENT';

-- RP4.3  Research funding received (₹ Lakhs).
--        NOTE: grant_amount lives on the SCHEME, and one scheme can fund many
--        projects. Two interpretations -- pick per NIRF guidance:

--   (a) Sum of DISTINCT scheme grants that have >=1 project (no double counting).
--       live: schemes 1 (30,000) + 3 (2,000,000) = ₹20.30 L
SELECT ROUND(SUM(s.grant_amount)/100000, 2) AS funding_lakhs_by_scheme
FROM   project_funding_agency_scheme s
WHERE  s.id IN (SELECT DISTINCT project_funding_agency_scheme_id
                FROM project WHERE is_draft = 0
                  AND project_funding_agency_scheme_id IS NOT NULL);

--   (b) Sum of grant attributed per project (counts a shared scheme once per project).
--       live: 3×30,000 + 2×2,000,000 = ₹40.90 L
SELECT ROUND(SUM(s.grant_amount)/100000, 2) AS funding_lakhs_by_project
FROM   project p
JOIN   project_funding_agency_scheme s ON s.id = p.project_funding_agency_scheme_id
WHERE  p.is_draft = 0;

-- RP4.4  Funding by agency type, by AY (grant_start_date drives the AY bucket).
SELECT a.agency_type,
       YEAR(s.grant_start_date)               AS grant_year,
       COUNT(DISTINCT s.id)                    AS schemes,
       ROUND(SUM(DISTINCT s.grant_amount)/100000, 2) AS funding_lakhs
FROM   project_funding_agency_scheme s
JOIN   project_funding_agency a ON a.id = s.project_funding_agency_id
GROUP  BY a.agency_type, YEAR(s.grant_start_date)
ORDER  BY grant_year, a.agency_type;

-- RP4.5  Funding agency / scheme inventory (sanity check -- currently test data).
SELECT s.id AS scheme_id, s.title AS scheme, s.grant_amount,
       s.grant_start_date, s.grant_end_date,
       a.agency_name, a.agency_type, a.region
FROM   project_funding_agency_scheme s
LEFT   JOIN project_funding_agency a ON a.id = s.project_funding_agency_id
ORDER  BY s.id;

-- Consultancy projects & consultancy/IPR revenue: not modelled / EXTERNAL (Finance ERP).


-- =====================================================================
-- Helper lookups
-- =====================================================================
-- Project themes:     SELECT id, title, project_code FROM project_type;
-- Funding agencies:   SELECT id, agency_name, agency_type, region FROM project_funding_agency;
-- All projects:       SELECT id, title, project_type_id, project_funding_agency_scheme_id,
--                            proposal_status, is_draft FROM project;
