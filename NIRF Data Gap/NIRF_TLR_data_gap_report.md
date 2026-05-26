# NIRF TLR Data Gap Report

**Source DB:** `collpoll_university` @ `digiidbcommon.c5sc77nejhmr.ap-south-1.rds.amazonaws.com`
**Spreadsheet:** NIRF Parameter 1 — Teaching, Learning & Resources (TLR), Weight: 30%
**Date:** 2026-05-26

This report maps every NIRF TLR cell to its data source. Cells marked **External** must be sourced from systems outside CollPoll (Finance ERP, Library Management System, IT/Admin records, HR system).

---

## TLR1 — Faculty-Student Ratio with Ph.D (FSR)

| Metric | Source | Confidence | Notes |
|---|---|---|---|
| Total Full-Time Faculty | DB: `faculty_profile` (164 rows) | Medium | No active/terminated flag. For historical AY snapshots (2021-22, 2022-23), need to infer active status via `staff_attendance_v2` activity or filter by `year_of_joining ≤ AY end`. Confirm with HR if `faculty_profile` only contains current full-time staff. |
| Total Students Enrolled | DB: `student_profile` + `ems_student_programme_enrollment` | High | Use `student_profile.year_of_joining` and `expected_year_of_passing` to compute "enrolled during AY X". Validate against `class_student` (4,804 rows). |
| Faculty with Ph.D | DB: `faculty_profile.qualification` (FK) | Low–Medium | `qualification` is an INT FK to an unidentified master table. Need to locate qualification master and map to Ph.D code. `faculty_research` table is empty — not a fallback. |
| Faculty-Student Ratio (FSR) | Derived | High | `Total Students / Total Faculty` |
| Ph.D Faculty Ratio | Derived | Medium | Depends on Ph.D resolution above |
| Qualifying Exam Qualified (GATE/NET) | **External** | — | No column in `faculty_profile` or related tables. Source from HR records. |
| Faculty with Experience > 5yr | DB: `faculty_profile.experience` (tinyint) | Medium | Filter `experience > 5`. Trustworthiness depends on whether HR keeps this field updated. |

---

## TLR2 — Financial Resources & Utilisation (FRU)

**Verdict: Entirely external.** CollPoll stores student-side money flow (fees received, payment gateway logs) — not institutional budget, capex, opex, or research-grant inflow.

| Metric | Source | Notes |
|---|---|---|
| Total Budget Received | **External — Finance ERP** | No `budget` table. `dues_finance` and `finance_*` tables are fee-receivable accounting, not sanctioned budget. |
| Capital Expenditure | **External — Finance ERP** | No capex table. |
| Recurring Expenditure | **External — Finance ERP / Payroll** | No salaries, admin, ops expenditure table. Faculty `staff_attendance_v2` exists but no salary disbursement records. |
| Research Funding Received | **External (or partial in DB)** | `project` (4 rows) and `project_funding_agency` (2 rows) exist but data is sparse. Schema supports it; data isn't there. Source from DST/SERB/ICSSR award letters. |
| Budget Utilisation % | Derived | Once budget + expenditure are sourced. |
| Budget per Student (₹ Lakhs) | Derived | Budget (external) / student count (DB). |

---

## TLR3 — Availability of Quality Teaching & Learning Infrastructure

| Metric | Source | Confidence | Notes |
|---|---|---|---|
| Classroom Seating Capacity | DB: `infrastructure_master.capacity` + `infrastructure_type` | High | 964 infra rows, 22 types. Filter `infrastructure_type` where category/identifier indicates classroom, then `SUM(capacity)`. |
| Smart Classrooms / ICT enabled | DB: `infrastructure_attributes` (12 attrs) | Low | Needs investigation. May exist as an attribute flag on classroom infra; if not, source from IT/Admin asset register. |
| Library Volumes (Books) | **External — Library Mgmt System** | — | `book`, `library`, `library_store`, `library_template` tables — **all 0 rows**. Source from Koha/SOUL/LibSys. |
| e-Journals / Databases | **External — Library Mgmt System** | — | No schema. Source from library's subscriptions list. |
| Laboratory Area (sq.m) | **External (or partial in DB)** | — | `infrastructure_master` has `capacity` (seats) but no `area_sqm`. Check `infrastructure_attributes` for an area attribute; if absent, source from Estate/Admin floor plans. |
| Internet Bandwidth (Mbps) | **External — IT/Admin** | — | No schema. Source from ISP contract / Network Admin. |
| Hostel Capacity | DB: `infrastructure_master` (type=hostel) | Medium | `hostel_room` is empty. Derive from `infrastructure_master` rows where `type_id` maps to hostel, or use `hostel_allotment` (131 rows) as a current-occupancy proxy. |

---

## Recommended Action Plan

### 1. Fillable from CollPoll (do now)
- Total faculty + total students per AY (TLR1)
- Classroom seating capacity (TLR3)
- Hostel capacity (TLR3, with caveat)
- Faculty experience >5yr (TLR1, with caveat)

### 2. Resolve via short DB investigation
- Find the qualification master table → enables Ph.D faculty count
- Inspect `infrastructure_attributes` → may yield smart classroom flag and/or lab area
- Inspect `infrastructure_type` rows → confirm classroom/lab/hostel categorisation

### 3. Request from other teams (parallelize)
| Owner | Items needed |
|---|---|
| Finance / Accounts | TLR2 entire block — Budget, Capex, Opex, Research Funding (per AY 2021-22, 2022-23, 2023-24, in ₹ Lakhs) |
| HR | Faculty GATE/NET qualifications; confirmation that `faculty_profile` reflects current full-time roster |
| Library | Book count, e-journal subscriptions, database subscriptions (per AY) |
| IT / Admin | Internet bandwidth (Mbps); ICT-enabled classroom count |
| Estate / Admin | Total laboratory area in sq.m |

---

## Database Connection Reference

- Host: `digiidbcommon.c5sc77nejhmr.ap-south-1.rds.amazonaws.com`
- DB: `collpoll_university`
- MCP config: [.mcp.json](.mcp.json)
- Discovery script: [nirf_db_check.py](nirf_db_check.py)
