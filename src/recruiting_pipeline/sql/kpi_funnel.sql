-- Hiring funnel: how many eligible applications reached each stage, and the
-- conversion from the previous stage.
--
-- Two cohorts, on purpose:
--   all_eligible         every trustworthy application, including candidates of open
--                        requisitions who are still in process (biases conversion down);
--   filled_requisitions  only requisitions that were filled, where outcomes are final.
-- stage_reached is the furthest stage, so an application "reached" stage s when its
-- rank is >= rank(s).

WITH cohorts AS (
    SELECT 'all_eligible' AS cohort, a.stage_rank
    FROM fact_application AS a
    WHERE a.kpi_eligible

    UNION ALL

    SELECT 'filled_requisitions' AS cohort, a.stage_rank
    FROM fact_application AS a
    JOIN dim_requisition AS r USING (req_id)
    WHERE a.kpi_eligible AND r.status = 'filled'
),
reached AS (
    SELECT
        c.cohort,
        s.stage,
        s.stage_rank,
        COUNT(*) FILTER (WHERE c.stage_rank >= s.stage_rank) AS reached
    FROM dim_stage AS s
    CROSS JOIN cohorts AS c
    GROUP BY c.cohort, s.stage, s.stage_rank
)
SELECT
    cohort,
    stage,
    stage_rank,
    reached,
    ROUND(reached::DOUBLE / FIRST_VALUE(reached) OVER w, 4) AS share_of_applicants,
    ROUND(reached::DOUBLE / LAG(reached) OVER w, 4)         AS conversion_from_previous
FROM reached
WINDOW w AS (PARTITION BY cohort ORDER BY stage_rank)
ORDER BY cohort, stage_rank;
