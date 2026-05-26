# NIRF GO Data Gap Report

**Source DB:** `collpoll_university` @ `digiidbcommon.c5sc77nejhmr.ap-south-1.rds.amazonaws.com`
**Spreadsheet:** NIRF Parameter 3 — Graduation Outcomes (GO), Weight: 20%
**Date:** 2026-05-26

This report maps every NIRF GO cell to its data source. **Best parameter so far for CollPoll data — GO2 (University Examinations) and GO3 placement counts are strongly fillable. GO4 is almost entirely external.**

---

## GO1 — Ph.D Students Graduated & Post-Doctoral Fellows (GPH)

| Metric | Source | Confidence | Notes |
|---|---|---|---|
| Ph.D Degrees Awarded | DB: phd module + `ems_examination_student_transcript` | Low | The `phd_*` module is wired up but data is thin: `phd_student_form_detail` (8 rows), `phd_student_thesis_detail` (3 rows), `phd_student_guide` (5 rows), `phd_template_programme` (2 rows). Better path: filter `student_profile.programme_id` → `programme` rows where programme type = PhD, then check graduation status via `student_status` or `expected_year_of_passing`. Validate with `ems_examination_student_transcript` (7 rows). |
| Post-Doctoral Fellows | **External — HR** | — | No table. CollPoll doesn't track post-doc appointments. Source from HR / Faculty office. |

---

## GO2 — Metric for University Examinations (GUE)

**Verdict: Strongly fillable from CollPoll.** The `ems_examination_student_*` family is the richest module in the DB for NIRF purposes.

| Metric | Source | Confidence | Notes |
|---|---|---|---|
| Students Appeared in UG Final Year | DB: `ems_examination_student` + `student_profile` | High | 296 exam-student rows. Join to `student_profile` filtered where programme is UG and `year = duration` (final year). |
| Students Passed in First Attempt | DB: `ems_examination_student_cgpa_percentage` | High | 122 rows. Filter where `re_exam_cgpa IS NULL` (no re-exam needed) AND `cgpa >= pass threshold`. |
| Pass Percentage | Derived | High | Passed / Appeared. |
| Students with ≥ 60% marks (First Class) | DB: `ems_examination_student_cgpa_percentage.cgpa` OR `ems_examination_student_year_percentage.percentage` | High | Direct filter `percentage >= 60`. 122 / 37 rows respectively. |
| Students with ≥ 75% marks (Distinction) | DB: same as above | High | Direct filter `percentage >= 75`. |

> **Caveat:** Row counts (122, 37, 296) are small relative to the total student population (1,541). Confirm that result tables are fully populated for AY 2021-22 → 2023-24 before publishing. May need to validate per-AY coverage with the Examinations Office.

---

## GO3 — Placement, Higher Studies & Entrepreneurship (GPHE)

**Verdict: Placement is strong, Higher Studies & Entrepreneurship are external.**

| Metric | Source | Confidence | Notes |
|---|---|---|---|
| Students Placed (On-Campus) | DB: `placement_student_status` (1,324) + `placement_application` (1,286) + `placement_offer_status` | High | Join `placement_application.offer_status_id` to `placement_offer_status` filtered to "Offered/Accepted" states. `placement_cycle` (5 rows) gives the AY context via `start_date`/`end_date`. |
| Students in Higher Studies | **External — Alumni survey / Registrar** | — | No tracking. `alumni_profile` has the right metadata (programme, batch) but **zero rows**, and even when populated, has no `currently_pursuing_degree` field. |
| Entrepreneurs / Self-employed | **External — Alumni survey** | — | No table. Standard NIRF practice is alumni self-declaration. |
| Median Salary (₹ LPA) | DB: `placement_job.ctc` + `placement_application` join | Medium | `placement_job` has `ctc`, `ctc_type` (enum: probably Annual/Monthly), `minimum_ctc_range`, `maximum_ctc_range`. CTC is stored per job, not per offer — assumption is each accepted offer pays the job's CTC. Compute median across placed students by joining placement_application(offered) → placement_job(ctc). |
| Max Salary (₹ LPA) | DB: `placement_job.ctc` (max across placed jobs) | Medium | Same source. `MAX(placement_job.ctc)` filtered to jobs with at least one accepted offer. |
| Placement Rate % | Derived | High | Placed / Eligible. Eligible count from `placement_eligible_programme` (7,622 rows — likely cycle×programme combinations, needs care) or via `placement_student_status` total. |

> **CTC caveat:** Some institutions negotiate per-student offer amounts that differ from the posted CTC. If true here, the salary numbers will be conservative. Check with the Placement Cell whether `placement_job.ctc` reflects the actual offered amount.

---

## GO4 — Metric for Professional Activities (GPA)

**Verdict: Almost entirely external.** CollPoll does not track post-graduation exam outcomes.

| Metric | Source | Notes |
|---|---|---|
| GATE Qualified Students | **External — Student self-declaration / Placement Cell** | No `gate_score` or similar field in `student_profile`. |
| Students clearing Professional Exams (UPSC, CAT, CFA) | **External — Alumni survey / Placement Cell** | No tracking. |
| Registered for PhD from UG batch | DB partial + External | Internal PhD registrations could come from `student_profile` filtered to PhD programmes where `joining_year` follows a UG completion year — but only captures students who joined this same institution. Students going to other institutions for PhD are external. |
| International Exposure (Abroad) | **External — International Office** | No `exchange`, `abroad`, or `internship` tables exist in CollPoll. Source from the International Programs / Exchange office. |

---

## Recommended Action Plan

### 1. Fillable from CollPoll (do now)
- **GO2 (entire block)** — UG appeared, passed first attempt, pass %, ≥60%, ≥75% — high confidence
- **GO3 placement counts and salary** — students placed, median CTC, max CTC, placement rate
- **GO1 Ph.D Degrees Awarded** — via `student_profile` + `programme` (PhD filter), with low-confidence caveat

### 2. Verification needed before publishing
- Confirm per-AY coverage of `ems_examination_student_*` tables with the Examinations Office (only 122-296 rows for 1,541 students)
- Confirm whether `placement_job.ctc` reflects negotiated per-student offer amounts or is a job-listing default

### 3. Request from other teams (parallelize)

| Owner | Items needed |
|---|---|
| HR / Faculty Office | Post-Doctoral Fellows count (per AY) |
| Alumni Office | Students in Higher Studies; Entrepreneurs / Self-employed; PhD pursuers at other institutions (alumni survey) |
| Placement Cell | GATE-qualified students count; UPSC/CAT/CFA cleared count |
| International Programs Office | Students with international exposure (exchange / internship abroad) per AY |
| Examinations Office | Confirm exam-result data completeness for AY 2021-22, 2022-23, 2023-24 |

### 4. Optional: populate CollPoll going forward

The `alumni_profile` table schema is wired but empty. If future NIRF cycles want higher-studies / entrepreneur / exchange data answered from CollPoll, the alumni module would need:
- An onboarding flow to populate `alumni_profile`
- New columns for: current_status (employed/higher_studies/entrepreneur/other), current_employer, degree_pursuing, country (already present)

Not relevant for the current submission.

---

## Database Connection Reference

- Host: `digiidbcommon.c5sc77nejhmr.ap-south-1.rds.amazonaws.com`
- DB: `collpoll_university`
- MCP config: [.mcp.json](.mcp.json)
- Related reports: [NIRF_TLR_data_gap_report.md](NIRF_TLR_data_gap_report.md), [NIRF_RP_data_gap_report.md](NIRF_RP_data_gap_report.md)
