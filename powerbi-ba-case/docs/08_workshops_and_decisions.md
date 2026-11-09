# 08 Stakeholder workshops and decision log

Simulated for this case. Three working sessions turned conflicting requests into one agreed scope. The decision log records what was decided, who agreed and why, so the definitions in `02_kpi_definitions.md` can be traced to a conversation.

## Workshop 1 — Discovery (60 min)

**Attendees:** retail sales lead, growth marketing manager, CX manager, finance business partner, BA (facilitator).
**Format:** each team listed the five numbers it asks for most often and the decision each number supports; the BA grouped duplicates on a shared board.

| Finding | Teams | What it showed |
|---|---|---|
| 31 recurring requests reduced to 14 distinct KPIs | All | Most requests were the same number cut a different way |
| "Revenue" meant three different things | Retail, finance | Gross sell-out, net sell-out, refill revenue |
| Quarter boundaries differed | Growth, finance | Calendar months vs ISO weeks |
| CX only tracked the average SLA | CX | No view by ticket type |
| Growth wanted cost per new member by channel | Growth | Members carry no channel tag |

**Prioritisation:** the group scored each KPI on decision value (high / medium / low) and data readiness (ready / needs fix / not available). High-value and ready items became the Must stories; "not available" items went to the decision log.

## Workshop 2 — Definitions and design review (90 min)

**Attendees:** same group plus the data governance lead and a data engineer.
**Inputs:** draft KPI sheet, page wireframes (`07_report_spec.md`), data-quality findings (`05_data_quality_report.md`).
**Outcome:** 14 definitions signed off, four page layouts approved with two changes: the CX table moved next to the ticket bar so categories can be compared in one glance, and a year-over-year panel was added to page 1 (US-10).

## Workshop 3 — UAT walkthrough (45 min)

Each stakeholder ran the tasks in `06_test_cases_uat.md` on the test build. Three issues were raised (UAT-01 to UAT-03) and resolved or deferred as recorded there.

## Decision log

| ID | Decision | Options considered | Why | Agreed by |
|---|---|---|---|---|
| D-01 | Retail revenue is **net of returns** | Gross (partner reports), net | Finance books net; gross overstates partners with high returns | Finance, retail |
| D-02 | Reporting calendar is **ISO weeks**, quarters are 13-week blocks | Calendar months, ISO weeks | Orders and partner files are weekly; both years then have 52 weeks for fair year-over-year | Finance, growth |
| D-03 | **Channel-level CAC is not built** in release 1 (US-07) | Split by last touch, split by spend share, defer | Any split would be a guess presented as fact; options for release 2 logged | Growth, governance |
| D-04 | Weeks below **95% partner store coverage** are excluded from retail KPIs and flagged | Show as is, estimate missing stores, exclude and flag | A late file looked like a sales drop in the pilot | Retail, data engineering |
| D-05 | **SLA counts resolved tickets only**; open tickets tracked separately in release 2 | Count open as missed, resolved only | Keeps the existing CX definition; open-ticket count deferred (UAT-02) | CX |
| D-06 | **Active member = an order in the last 8 weeks**; lapsed = 12+ weeks since last order | 4, 8 or 12 weeks | The median gap between refill orders is 4 weeks and 75% of gaps are 7 weeks or less, so 8 weeks keeps normal buyers active; 90% of gaps are 10 weeks or less, so 12+ weeks marks members who have likely stopped | Growth |
| D-07 | **CX SLA target = 85%** resolved within 3 days | 80%, 85%, 90% | Matches the CX team's existing service commitment | CX |
| D-08 | Holdout-suppressed CRM records are **not sends** | Count all records, count sends only | Suppressed records were never delivered | Growth |
| D-09 | Fix data issues in the pipeline, **never by hand** in the report | Manual fixes, pipeline rules | Fixes must repeat on every refresh and be visible on page 4 | Governance, data engineering |
