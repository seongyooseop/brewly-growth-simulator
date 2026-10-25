-- BREWLY marts: raw member events -> tables for monitoring, experiments, modelling.
-- Run with src/build_marts.py (DuckDB). Raw files are registered as views: members, orders,
-- crm_sends, experiment_groups, marketing_spend, calendar. Weeks are numbered 0-103 from 2024-01-01.

-- Week index ------------------------------------------------------------------------------
CREATE OR REPLACE TABLE weeks AS
SELECT DISTINCT CAST(week_start AS DATE) AS week_start,
       CAST(datediff('day', DATE '2024-01-01', CAST(week_start AS DATE)) / 7 AS INTEGER) AS week
FROM calendar;

CREATE OR REPLACE TABLE regions AS SELECT DISTINCT region FROM calendar;

-- Active members (observable definition): ordered in the last 8 weeks, or joined in the last 8 weeks.
-- True churn is never observed, so CRM teams use a recency window like this one.
CREATE OR REPLACE TABLE member_active_weeks AS
SELECT DISTINCT o.member_id, m.region, o.week + k.k AS week
FROM orders o
JOIN members m USING (member_id)
CROSS JOIN range(0, 8) AS k(k)
WHERE o.week + k.k <= 103
UNION
SELECT m.member_id, m.region, m.join_week + k.k AS week
FROM members m
CROSS JOIN range(0, 8) AS k(k)
WHERE m.join_week >= 0 AND m.join_week + k.k <= 103;

-- Weekly region table: the input of the marketing-mix model -------------------------------
CREATE OR REPLACE TABLE weekly_region AS
WITH grid AS (
    SELECT w.week, w.week_start, r.region FROM weeks w CROSS JOIN regions r
), joins AS (
    SELECT region, join_week AS week, count(*) AS new_members FROM members WHERE join_week >= 0 GROUP BY ALL
), ords AS (
    SELECT m.region, o.week, count(*) AS capsule_orders
    FROM orders o JOIN members m USING (member_id) GROUP BY ALL
), active AS (
    SELECT region, week, count(*) AS active_members FROM member_active_weeks GROUP BY ALL
), crm AS (
    SELECT m.region, s.week,
           count(*) FILTER (WHERE s.send_type IN ('trigger', 'boost')) AS crm_sends,
           count(*) FILTER (WHERE s.send_type = 'boost') AS crm_boost_sends,
           count(*) FILTER (WHERE s.send_type = 'suppressed') AS crm_suppressed,
           -- members the running-low journey selected, whether or not the holdout suppressed the message
           count(*) FILTER (WHERE s.send_type IN ('trigger', 'suppressed')) AS crm_eligible
    FROM crm_sends s JOIN members m USING (member_id) GROUP BY ALL
), spend AS (
    PIVOT (SELECT CAST(week_start AS DATE) AS week_start, region, channel, spend FROM marketing_spend)
    ON channel USING sum(spend)
)
SELECT g.week, g.week_start, g.region,
       coalesce(j.new_members, 0) AS new_members,
       coalesce(o.capsule_orders, 0) AS capsule_orders,
       coalesce(a.active_members, 0) AS active_members,
       coalesce(c.crm_sends, 0) AS crm_sends,
       coalesce(c.crm_boost_sends, 0) AS crm_boost_sends,
       coalesce(c.crm_suppressed, 0) AS crm_suppressed,
       coalesce(c.crm_eligible, 0) AS crm_eligible,
       s.referral AS spend_referral, s.store_trial AS spend_store_trial,
       s.retail_partner AS spend_retail_partner, s.events AS spend_events,
       coalesce(c.crm_sends, 0) * getvariable('cost_per_send') AS spend_crm,
       cal.category_interest, cal.event_promo, cal.holiday_lny, cal.holiday_chuseok
FROM grid g
LEFT JOIN joins j USING (region, week)
LEFT JOIN ords o USING (region, week)
LEFT JOIN active a USING (region, week)
LEFT JOIN crm c USING (region, week)
LEFT JOIN spend s ON s.region = g.region AND s.week_start = g.week_start
LEFT JOIN calendar cal ON cal.region = g.region AND CAST(cal.week_start AS DATE) = g.week_start
ORDER BY g.region, g.week;

-- Monthly join cohorts: orders per member by 4-week period since joining -------------------
-- Periods of exactly 4 weeks (13 a year) keep every column the same length; only 2024 cohorts,
-- so every cohort has a full year of history.
CREATE OR REPLACE TABLE cohort_monthly AS
WITH m AS (
    SELECT member_id, region, join_week, CAST(floor(join_week / (52.0 / 12)) AS INTEGER) AS cohort_month
    FROM members WHERE join_week BETWEEN 0 AND 51
), sizes AS (
    SELECT cohort_month, count(*) AS cohort_size FROM m GROUP BY ALL
), ev AS (
    SELECT m.cohort_month, m.member_id, CAST(floor((o.week - m.join_week) / 4) AS INTEGER) AS period
    FROM orders o JOIN m USING (member_id)
    WHERE o.week >= m.join_week AND o.week < m.join_week + 52
)
SELECT ev.cohort_month, ev.period, s.cohort_size,
       count(DISTINCT ev.member_id) AS ordering_members, count(*) AS orders
FROM ev JOIN sizes s USING (cohort_month)
GROUP BY ALL ORDER BY 1, 2;

-- Lifecycle funnel by join quarter --------------------------------------------------------
CREATE OR REPLACE TABLE lifecycle_funnel AS
WITH m AS (
    SELECT member_id, join_week, CAST(floor(join_week / 13) AS INTEGER) AS join_quarter
    FROM members WHERE join_week BETWEEN 0 AND 77   -- needs 26 weeks of follow-up
), o AS (
    SELECT o.member_id, o.week - m.join_week AS wk FROM orders o JOIN m USING (member_id) WHERE o.week >= m.join_week
), per AS (
    SELECT m.join_quarter, m.member_id,
           count(*) FILTER (WHERE wk < 4) > 0 AS first_order_4w,
           count(*) FILTER (WHERE wk < 13) >= 3 AS three_orders_13w,
           count(*) FILTER (WHERE wk BETWEEN 22 AND 25) > 0 AS ordering_month_6
    FROM m LEFT JOIN o USING (member_id) GROUP BY ALL
)
-- Each stage includes the previous one, so the funnel only narrows.
SELECT join_quarter, count(*) AS registered,
       sum(first_order_4w::INT) AS first_order_4w,
       sum((first_order_4w AND three_orders_13w)::INT) AS three_orders_13w,
       sum((first_order_4w AND three_orders_13w AND ordering_month_6)::INT) AS ordering_month_6
FROM per GROUP BY ALL ORDER BY 1;

-- Experiment members: intention-to-treat population and outcomes ---------------------------
-- Population: members active (by the 8-week rule) when the test started, plus members who joined
-- during the test. Both are fixed before any outcome, so the comparison stays randomised.
CREATE OR REPLACE TABLE experiment_members AS
WITH tests AS (
    SELECT * FROM (VALUES ('crm_holdout_w80', 80, 8), ('crm_frequency_w92', 92, 6)) t(experiment, start_week, n_weeks)
), pop AS (
    SELECT t.experiment, t.start_week, t.n_weeks, a.member_id, a.region
    FROM tests t JOIN member_active_weeks a ON a.week = t.start_week
    UNION
    SELECT t.experiment, t.start_week, t.n_weeks, m.member_id, m.region
    FROM tests t JOIN members m ON m.join_week > t.start_week AND m.join_week < t.start_week + t.n_weeks
)
SELECT p.experiment, p.region, p.member_id, g."group",
       (SELECT count(*) FROM orders o WHERE o.member_id = p.member_id
            AND o.week >= p.start_week AND o.week < p.start_week + p.n_weeks) AS orders_in_window,
       (SELECT count(*) FROM orders o WHERE o.member_id = p.member_id
            AND o.week >= p.start_week - 12 AND o.week < p.start_week) AS orders_pre_12w,
       (SELECT count(*) FROM crm_sends s WHERE s.member_id = p.member_id AND s.send_type <> 'suppressed'
            AND s.week >= p.start_week AND s.week < p.start_week + p.n_weeks) AS sends_in_window
FROM pop p JOIN experiment_groups g ON g.member_id = p.member_id AND g.experiment = p.experiment;

-- Uplift training table: members the journey triggered during the holdout test --------------
-- Randomised: among triggered members, the holdout group got no message. Features are as of week 80.
CREATE OR REPLACE TABLE uplift_training AS
WITH trig AS (
    SELECT DISTINCT member_id FROM crm_sends WHERE week BETWEEN 80 AND 87
), last_order AS (
    SELECT member_id, max(week) AS last_week FROM orders WHERE week < 80 GROUP BY ALL
)
SELECT m.member_id, m.region, m.age_band, m.device_model,
       80 - m.join_week AS tenure_weeks,
       coalesce(80 - l.last_week, 80 - m.join_week) AS recency_weeks,
       (SELECT count(*) FROM orders o WHERE o.member_id = m.member_id AND o.week BETWEEN 68 AND 79) AS orders_12w,
       (SELECT count(*) FROM orders o WHERE o.member_id = m.member_id AND o.week BETWEEN 54 AND 79) AS orders_26w,
       (SELECT count(*) FROM crm_sends s WHERE s.member_id = m.member_id AND s.send_type <> 'suppressed'
            AND s.week BETWEEN 72 AND 79) AS sends_8w,
       CASE WHEN g."group" = 'holdout' THEN 0 ELSE 1 END AS treated,
       (SELECT count(*) FROM orders o WHERE o.member_id = m.member_id AND o.week BETWEEN 80 AND 87) AS orders_8w
FROM trig t
JOIN members m USING (member_id)
LEFT JOIN last_order l USING (member_id)
JOIN experiment_groups g ON g.member_id = m.member_id AND g.experiment = 'crm_holdout_w80'
WHERE m.join_week <= 79;
