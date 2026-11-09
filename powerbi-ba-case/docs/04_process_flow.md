# 04 Delivery process

How a data request becomes a data product in this case. Ad hoc questions are answered and logged; recurring needs go through requirements, data readiness, testing and UAT before release.

```mermaid
flowchart TD
    A[Request from a business team] --> B{Triage by BA:<br/>one-off or recurring?}
    B -- One-off --> C[Answer with an ad hoc analysis<br/>and log the request]
    C --> R[(Request log)]
    R -- Same question 3+ times --> D
    B -- Recurring --> D[Discovery interviews<br/>with stakeholders]
    D --> E[Business requirements<br/>and KPI definitions]
    E --> F[Governance sign-off<br/>of definitions]
    F --> G{Data readiness:<br/>quality checks pass?}
    G -- No --> H[Fix with data engineering<br/>or flag in the model]
    H --> G
    G -- Yes --> I[Build model and report]
    I --> J{Functional test:<br/>measures match SQL?}
    J -- No --> I
    J -- Yes --> K{UAT with stakeholders:<br/>signed off?}
    K -- Changes --> E
    K -- Yes --> L[Release and walkthrough<br/>for each team]
    L --> M[Adoption review after 4 weeks:<br/>usage and remaining requests]
    M --> R
```

## RACI

R = responsible, A = accountable, C = consulted, I = informed.

| Step | Business Analyst | Business stakeholders | Data engineering | Data governance | Data analyst |
|---|---|---|---|---|---|
| Triage and request log | A/R | C | I | I | C |
| Discovery interviews | A/R | C | I | I | C |
| Requirements and KPI definitions | A/R | C | C | C | C |
| Definition sign-off | R | C | I | A | I |
| Data-quality checks and fixes | R | I | A/R | C | C |
| Model and report build | A/R | I | C | I | C |
| Functional test | A/R | I | C | I | R |
| UAT and sign-off | R | A | I | I | C |
| Release and adoption review | A/R | C | I | I | C |
