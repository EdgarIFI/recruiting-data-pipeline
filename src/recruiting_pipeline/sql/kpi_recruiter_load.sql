-- Recruiter workload at the snapshot date:
--   open_requisitions    requisitions still open, by owner
--   active_candidates    trustworthy applications still in process on those requisitions
--   activities_last_30d  CRM activities logged in the 30 days before the snapshot

WITH recruiters AS (
    SELECT recruiter_id FROM dim_requisition
    UNION
    SELECT recruiter_id FROM fact_crm_activity
),
open_reqs AS (
    SELECT recruiter_id, COUNT(*) AS n
    FROM dim_requisition
    WHERE status = 'open'
    GROUP BY recruiter_id
),
active AS (
    SELECT r.recruiter_id, COUNT(*) AS n
    FROM fact_application AS a
    JOIN dim_requisition  AS r USING (req_id)
    WHERE a.kpi_eligible
      AND a.outcome = 'in_process'
      AND r.status = 'open'
    GROUP BY r.recruiter_id
),
recent AS (
    SELECT c.recruiter_id, COUNT(*) AS n
    FROM fact_crm_activity AS c
    CROSS JOIN params AS p
    WHERE c.kpi_eligible
      AND c.activity_at > p.as_of - INTERVAL 30 DAY
    GROUP BY c.recruiter_id
)
SELECT
    rc.recruiter_id,
    COALESCE(o.n, 0)                                         AS open_requisitions,
    COALESCE(a.n, 0)                                         AS active_candidates,
    COALESCE(x.n, 0)                                         AS activities_last_30d,
    ROUND(COALESCE(a.n, 0)::DOUBLE / NULLIF(o.n, 0), 1)      AS active_candidates_per_open_req
FROM recruiters AS rc
LEFT JOIN open_reqs AS o USING (recruiter_id)
LEFT JOIN active    AS a USING (recruiter_id)
LEFT JOIN recent    AS x USING (recruiter_id)
ORDER BY active_candidates DESC, recruiter_id;
