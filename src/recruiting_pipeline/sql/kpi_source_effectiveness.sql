-- Source effectiveness on filled requisitions (final outcomes only).
--
-- interview_rate = share of applications that reached the interview stage
-- hire_rate      = share of applications that ended in a hire
-- Each rate comes with a 95% Wilson interval: with a few hundred applications per
-- source and hire rates of a few percent, the uncertainty is as important as the
-- point estimate. Overlapping intervals mean "no evidence of a difference".

WITH base AS (
    SELECT
        a.source,
        COUNT(*)                                     AS applications,
        COUNT(*) FILTER (WHERE a.stage_rank >= 2)    AS reached_interview,
        COUNT(*) FILTER (WHERE a.outcome = 'hired')  AS hires
    FROM fact_application AS a
    JOIN dim_requisition  AS r USING (req_id)
    WHERE a.kpi_eligible
      AND r.status = 'filled'
    GROUP BY a.source
)
SELECT
    source,
    applications,
    reached_interview,
    hires,
    ROUND(reached_interview::DOUBLE / applications, 4)       AS interview_rate,
    ROUND(wilson_low(reached_interview, applications), 4)    AS interview_rate_low,
    ROUND(wilson_high(reached_interview, applications), 4)   AS interview_rate_high,
    ROUND(hires::DOUBLE / applications, 4)                   AS hire_rate,
    ROUND(wilson_low(hires, applications), 4)                AS hire_rate_low,
    ROUND(wilson_high(hires, applications), 4)               AS hire_rate_high
FROM base
ORDER BY interview_rate DESC, source;
