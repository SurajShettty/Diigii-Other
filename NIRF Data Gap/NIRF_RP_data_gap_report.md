# NIRF RP Data Gap Report

**Source DB:** `collpoll_university` @ `digiidbcommon.c5sc77nejhmr.ap-south-1.rds.amazonaws.com`
**Spreadsheet:** NIRF Parameter 2 — Research & Professional Practice (RP), Weight: 30%
**Date:** 2026-05-26

This report maps every NIRF RP cell to its data source. **Verdict up front: this entire parameter is effectively external — CollPoll has no publication, citation, or patent data, and the project/funding module is empty (4 project rows, 2 funding scheme rows).**

---

## RP1 — Combined Metric for Research Publication (PU)

**Verdict: Entirely external — bibliometric databases.** CollPoll has zero publication tables. Searches for `publication`, `scopus`, `wos`, `journal`, `citation`, `paper` returned only exam-paper tables (`ems_assessment_question_paper_*`) and accounting ledger entries — none relevant.

| Metric | Source | Notes |
|---|---|---|
| Scopus-indexed Publications | **External — Scopus API** | Pull via `https://api.elsevier.com/content/search/scopus` filtered by institution AF-ID. |
| Web of Science Publications | **External — WoS API / InCites** | Pull via Clarivate WoS API filtered by institution. |
| Combined PU Score | Derived | NIRF formula: weighted Scopus + WoS, de-duplicated. |
| Publications per Faculty | Derived | Total publications / Total faculty (faculty count from CollPoll `faculty_profile`). |

> **Note:** The `faculty_research` table has a publication-ish schema (`title`, `year`, `publisher`, `isbn`, `doi`, `issn_print`, `issn_online`) but **zero rows** — the module is unused. If the institution wants self-reported publications visible in CollPoll, this table is the place; for NIRF, Scopus/WoS are the authoritative source.

---

## RP2 — Combined Metric for Quality of Publications (QP)

**Verdict: Entirely external — bibliometric databases.**

| Metric | Source | Notes |
|---|---|---|
| h-index (Scopus) | **External — Scopus** | Institution h-index from Scopus. |
| Citations (Scopus/WoS) | **External — Scopus / WoS** | Sum of citations across all institution-affiliated papers. |
| Highly-Cited Papers (HCP) | **External — InCites / Scopus** | Papers in top 10% citation percentile globally for their field/year. |
| Avg. Citation per Paper | Derived | Total citations / Total papers. |

---

## RP3 — IPR & Patents (IPR)

**Verdict: Entirely external.** Zero tables matching `patent`, `ipr`, `intellectual`, `license`.

| Metric | Source | Notes |
|---|---|---|
| Patents Filed | **External — IPR Cell / Patent attorney records** | Track via institution's IP cell or Indian Patent Office (IPO) e-filing portal. |
| Patents Granted | **External — IPR Cell / IPO** | Granted patents on IPO India / WIPO. |
| Patents Commercialised | **External — IPR Cell / Tech Transfer Office** | Patents with active licensing agreements generating revenue. |
| IPR Revenue (₹ Lakhs) | **External — Finance ERP / TTO** | Revenue from IP licensing per AY. |

---

## RP4 — Footprint of Projects & Professional Practice (FPPP)

**Verdict: Schema exists in CollPoll but is essentially empty.** A `project` module is wired up — could be the system of record going forward — but current data is too sparse for NIRF reporting.

| Metric | Source | Confidence | Notes |
|---|---|---|---|
| Sponsored Research Projects (Govt.) | DB: `project` + `project_funding_agency.agency_type` | Very Low | Only **4 project rows**, **2 funding agencies**. `agency_type` is an enum that likely includes Govt/Industry/Private classification — could filter sponsored vs consultancy. Schema is suitable but unused. |
| Industry Consultancy Projects | DB: `project` + `project_funding_agency.agency_type='Industry'` | Very Low | Same — schema supports but data not populated. No separate consultancy table. |
| Research Funding Received (₹ Lakhs) | DB: `project_funding_agency_scheme.grant_amount` | Very Low | Has `grant_amount`, `currency_id`, `grant_start_date`, `grant_end_date` — perfect schema, but only 2 scheme rows. Source actuals from DST/SERB/ICSSR award letters + Finance ERP. |
| Consultancy Revenue (₹ Lakhs) | **External — Finance ERP** | — | No separate consultancy revenue tracking. Source from Finance. |

---

## Recommended Action Plan

### 1. Fillable from CollPoll
**None.** This entire parameter requires external data.

### 2. External sources required (parallelize)

| Owner | Items needed | System / Source |
|---|---|---|
| Research Office / Library | Scopus & WoS publication counts, h-index, total citations, HCP count per AY (2021-22, 2022-23, 2023-24) | Scopus API, WoS / InCites, or institutional Scopus dashboard. Need institution AF-ID. |
| IPR Cell / Tech Transfer Office | Patents filed, granted, commercialised per AY; IPR revenue | Internal IP cell register; IPO India e-filing portal |
| Research Office | Sponsored research projects (Govt. funded), grant amounts received per AY | DST/SERB/ICSSR/ICMR award letters; sanction orders |
| Research Office / Consultancy Cell | Industry consultancy projects + revenue per AY | MOU register; Finance ERP for revenue figures |
| Finance / Accounts | IPR revenue + Consultancy revenue per AY (₹ Lakhs) | Finance ERP |

### 3. Optional: populate CollPoll going forward

If the institution wants research data in CollPoll for future NIRF cycles, two unused-but-ready modules:
- **`faculty_research`** — schema supports publications (title, year, DOI, ISSN, ISBN, publisher). Currently 0 rows.
- **`project` + `project_funding_agency_scheme`** — supports sponsored projects with grant amounts, tenure, funding agency type. Currently 4 / 2 rows.

Populating these would let TLR2 (Research Funding) and RP4 (Sponsored Projects, Funding Received) be answered from CollPoll in future cycles. Not relevant for the current submission.

---

## Database Connection Reference

- Host: `digiidbcommon.c5sc77nejhmr.ap-south-1.rds.amazonaws.com`
- DB: `collpoll_university`
- MCP config: [.mcp.json](.mcp.json)
- Related: [NIRF_TLR_data_gap_report.md](NIRF_TLR_data_gap_report.md)
