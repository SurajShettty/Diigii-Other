# NIRF OI Data Gap Report

**Source DB:** `collpoll_university` @ `digiidbcommon.c5sc77nejhmr.ap-south-1.rds.amazonaws.com`
**Spreadsheet:** NIRF Parameter 4 — Outreach & Inclusivity (OI), Weight: 10%
**Date:** 2026-05-26

This report maps every NIRF OI cell to its data source. **Verdict up front: OI1, OI2, and OI3 are mostly fillable from CollPoll — `student_profile` and `faculty_profile` carry domicile, nationality, gender, caste, and income fields. OI4 (Disabilities) is entirely external — CollPoll does not track disability status.**

---

## OI1 — Regional Diversity (RD)

**Verdict: Strongly fillable.** `student_profile` carries all needed fields.

| Metric | Source | Confidence | Notes |
|---|---|---|---|
| Students from same state | DB: `student_profile.state_of_domicile` (or `domicile`) | High | Filter where domicile = institution's home state. NIRF uses domicile state, not current address. |
| Students from other states | DB: `student_profile.state_of_domicile` | High | Inverse of above; exclude international (citizenship ≠ India). |
| International Students | DB: `student_profile.nationality` + `citizenship` | High | Filter where citizenship is non-Indian. Cross-check with `passport_number`, `visa_number` (also on `student_profile`) for international student visa-holders. |
| Regional Diversity Index | Derived | High | NIRF formula: % other-state + % international, weighted. |

> **Caveat:** `state_of_domicile` may be sparsely populated for older batches. Validate with a `COUNT(*) WHERE state_of_domicile IS NULL` per AY before reporting.

---

## OI2 — Women Diversity (WD)

**Verdict: Strongly fillable.** Direct enum filter.

| Metric | Source | Confidence | Notes |
|---|---|---|---|
| Total Women Students | DB: `student_profile.gender` (enum) | High | `WHERE gender = 'Female'`. Filter by `year_of_joining` / `expected_year_of_passing` for AY context. |
| Women Faculty (Regular) | DB: `faculty_profile.gender` (enum) | High | `WHERE gender = 'Female'`. "Regular" filter via `designation` if HR distinguishes guest/visiting faculty (verify designation values). |
| % Women Students | Derived | High | Women students / Total students. |
| % Women Faculty | Derived | High | Women faculty / Total faculty. |

---

## OI3 — Economically & Socially Challenged Students (ESCS)

**Verdict: Mostly fillable from CollPoll, but data completeness needs verification.**

| Metric | Source | Confidence | Notes |
|---|---|---|---|
| SC Students | DB: `student_profile.caste` / `admission_category` + `student_admission_category` (1,607 rows) | Medium-High | Filter where `admission_category = 'SC'` or `caste IN ('SC list')`. `student_admission_category` is the explicit categorization table — prefer it over the free-text `caste` field. |
| ST Students | Same as above | Medium-High | Filter `admission_category = 'ST'`. |
| OBC Students | Same as above | Medium-High | Filter `admission_category = 'OBC'` (or sub-categories like OBC-A/OBC-B if the institution uses them). |
| EWS Students | DB: `student_profile.admission_category` OR derived from `parents_income` / `father_annual_income` | Medium | If `admission_category='EWS'` is explicitly tagged, use that. Otherwise EWS is defined by parental income < ₹8 Lakhs threshold — filter `parents_income < 800000`. The explicit category is the NIRF-compliant source. |
| Scholarship Recipients | DB: `student_scholarship` (39 rows) + `scholarship` (19) + `scholarship_component` (41) | Medium | Count distinct `ukid` from `student_scholarship` where `approved_amount > 0`. 39 rows may be only the latest cycle — verify per-AY coverage. |
| Fee Waiver / Concession granted (₹ Lakhs) | DB: `student_fee_waiver.waiver_amount` + `fee_student_discount.amount` | Low | `student_fee_waiver` has only **2 rows**, `fee_student_discount` is **empty**. Either waivers are rarely used at this institution OR data hasn't been entered. Verify with Finance. |

> **Caveat on EWS:** NIRF treats EWS as a distinct admission category, not just an income filter. Use `admission_category='EWS'` if it exists; fall back to income-based derivation only if explicit categorization isn't populated.

---

## OI4 — Facilities for Persons with Disabilities (FPHD)

**Verdict: Entirely external.** CollPoll has no disability tracking.

| Metric | Source | Notes |
|---|---|---|
| Students with Disabilities | **External — Admissions Office / Student Welfare** | `student_profile` has **no disability column**. Searches for `disab`, `divyaang`, `accessib`, `special_need`, `pwd` returned only `disable_library` (0 rows, unrelated — appears to be a feature-disable flag, not a disability registry). |
| Barrier-free campus features (ramps, lifts, accessible toilets) | **External — Estate / Admin** | Not in DB. Could be added as attributes on `infrastructure_master` via `infrastructure_attributes` for future cycles, but currently not tracked. |
| Assistive Technology available (Braille, screen readers) | **External — Library / IT** | Not in DB. Source from Library accessibility services and IT asset register. |

---

## Recommended Action Plan

### 1. Fillable from CollPoll (do now)
- **OI1 (entire block)** — Regional Diversity from `student_profile.state_of_domicile`, `nationality`, `citizenship`
- **OI2 (entire block)** — Women Students/Faculty from gender enums on both profiles
- **OI3 SC / ST / OBC / EWS counts** — from `student_profile.admission_category` + `student_admission_category` table
- **OI3 Scholarship Recipients** — from `student_scholarship` (with caveat on AY coverage)

### 2. Verification needed before publishing
- Confirm `state_of_domicile` completeness per AY in `student_profile`
- Confirm `admission_category` uses canonical values (`SC`, `ST`, `OBC`, `EWS`, `General`) vs free-text variants
- Confirm whether the institution actually grants few fee waivers (2 rows) OR whether the data isn't being entered (Finance check)
- Confirm `faculty_profile` covers only regular faculty (not guest/visiting) for "Women Faculty (Regular)" count

### 3. Request from other teams

| Owner | Items needed |
|---|---|
| Admissions / Student Welfare | Count of students with disabilities per AY (divyaang students) |
| Estate / Admin | Inventory of barrier-free features — ramps, lifts, accessible toilets, signage |
| Library / IT | Assistive technology inventory — Braille readers, screen readers, magnification software |
| Finance | Verify fee-waiver / concession totals per AY (CollPoll shows only 2 rows) |

### 4. Optional: populate CollPoll going forward

For future NIRF cycles, add to `student_profile`:
- `disability_status` (enum: None/Locomotor/Visual/Hearing/etc.)
- `disability_percentage` (int)
- `pwd_certificate_number` (varchar)

And add `accessibility_features` attribute group to `infrastructure_attributes` to tag classrooms/buildings as barrier-free.

---

## Database Connection Reference

- Host: `digiidbcommon.c5sc77nejhmr.ap-south-1.rds.amazonaws.com`
- DB: `collpoll_university`
- MCP config: [.mcp.json](.mcp.json)
- Related reports: [NIRF_TLR_data_gap_report.md](NIRF_TLR_data_gap_report.md), [NIRF_RP_data_gap_report.md](NIRF_RP_data_gap_report.md), [NIRF_GO_data_gap_report.md](NIRF_GO_data_gap_report.md)
