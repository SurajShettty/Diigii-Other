# NIRF PR Data Gap Report

**Source DB:** `collpoll_university` @ `digiidbcommon.c5sc77nejhmr.ap-south-1.rds.amazonaws.com`
**Spreadsheet:** NIRF Parameter 5 — Peer Perception (PR), Weight: 10%
**Date:** 2026-05-26

This report maps every NIRF PR cell to its data source. **Verdict up front: 100% external. NIRF conducts perception surveys centrally — no institution-side data feeds this parameter. The spreadsheet itself notes this.**

---

## PR1 — Peer Perception: Academic Reputation

**Verdict: Entirely external.** Searches for `mou`, `collaborat`, `partner`, `ranking`, `accreditat`, `recogniti`, `award`, `foreign`, `international` returned **zero matching tables**. The `survey_*` tables in CollPoll are internal campus feedback surveys (e.g., student satisfaction), not NIRF peer-perception surveys.

| Metric | Source | Notes |
|---|---|---|
| Academic Survey Respondents | **External — NIRF (NBA/MoE)** | NIRF mails surveys to a list of academics nominated by participating institutions and other peer institutions. Institutions cannot extract or estimate this number — only NIRF knows respondent counts. |
| Academic Reputation Score | **External — NIRF** | Computed by NIRF from the academic survey responses. Released only as part of the final NIRF result. |
| Employer Survey Respondents | **External — NIRF** | NIRF surveys employers from a centrally-maintained list. Same as above. |
| Employer Reputation Score | **External — NIRF** | Computed by NIRF from employer survey responses. |
| Industry Recognition | **External — Awards / Accreditation Cell** | Accolades from NBA, NAAC, professional bodies (IEEE, IET, ICAI, etc.). Not in CollPoll. Track via institution's Accreditation Cell records. |
| Media & Public Visibility | **External — PR / Communications Office** | Press mentions, NIRF rank YoY change. Track via PR agency monitoring, Google News, NIRF historical results. |
| International Collaborations | **External — International Programs Office** | Active MoUs with foreign universities. CollPoll has **no `mou`, `collaboration`, `partner`, or `foreign_institution` tables**. Source from IPO's MoU register. |
| Global Ranking Mentions | **External — Rankings dashboards** | QS World University Rankings, Times Higher Education (THE), Shanghai ARWU — institution-level data on each ranking body's website / API. |

---

## Why this parameter is structurally different

Unlike the other four NIRF parameters, **PR is not a data-submission parameter for institutions** — it is a perception-measurement parameter conducted by NIRF (Ministry of Education) directly. The institution does not fill these cells in the NIRF DCF (Data Capture Format); NIRF populates them from its own survey infrastructure.

The spreadsheet's own footnote confirms this:
> *"Perception scores are collected by NIRF centrally via surveys. Institutions cannot directly influence this score but can improve visibility through research output, rankings, and industry [recognition]."*

What institutions CAN do to improve PR:
1. **Increase research visibility** (drives RP scores, which in turn drives peer awareness) — see [NIRF_RP_data_gap_report.md](NIRF_RP_data_gap_report.md)
2. **Track and publicize accreditations** (NBA, NAAC, ABET, etc.)
3. **Sign and maintain international MoUs** — could be added as a CollPoll module for future tracking
4. **Submit to global rankings** (QS, THE, ARWU) — being ranked itself improves perception
5. **PR / media outreach** to ensure positive coverage in academic press

---

## Recommended Action Plan

### 1. Fillable from CollPoll
**None.** Entire parameter is external.

### 2. Cells the institution can populate for its own internal tracking (not for NIRF submission)

These cells can be filled in the spreadsheet by the institution for self-monitoring, even though NIRF computes the official score:

| Cell | Owner | Source |
|---|---|---|
| Industry Recognition | Accreditation Cell | NBA / NAAC / professional body certificates |
| Media & Public Visibility | PR / Communications Office | Press clipping archive; NIRF historical rank from `nirfindia.org` |
| International Collaborations | International Programs Office (IPO) | MoU register; list of active student/faculty exchange partners |
| Global Ranking Mentions | IQAC / Rankings cell | QS, THE, ARWU institution pages |

### 3. Cells the institution cannot fill at all

| Cell | Released by | When |
|---|---|---|
| Academic Survey Respondents | NIRF | Only via NIRF's final result release |
| Academic Reputation Score | NIRF | Only via NIRF's final result release |
| Employer Survey Respondents | NIRF | Only via NIRF's final result release |
| Employer Reputation Score | NIRF | Only via NIRF's final result release |

### 4. Optional: build a CollPoll module for international collaborations

For future cycles, a simple `institution_mou` table would help track:
- Partner institution name + country
- MoU type (research, exchange, dual-degree, internship)
- Signed date, expiry date, status (active/expired/under-renewal)
- Active student/faculty count under the MoU per AY

This would also feed GO4 (International Exposure) — see [NIRF_GO_data_gap_report.md](NIRF_GO_data_gap_report.md).

---

## Database Connection Reference

- Host: `digiidbcommon.c5sc77nejhmr.ap-south-1.rds.amazonaws.com`
- DB: `collpoll_university`
- MCP config: [.mcp.json](.mcp.json)
- Related reports: [NIRF_TLR_data_gap_report.md](NIRF_TLR_data_gap_report.md), [NIRF_RP_data_gap_report.md](NIRF_RP_data_gap_report.md), [NIRF_GO_data_gap_report.md](NIRF_GO_data_gap_report.md), [NIRF_OI_data_gap_report.md](NIRF_OI_data_gap_report.md)
