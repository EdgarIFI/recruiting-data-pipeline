-- Aging of open requisitions at the snapshot date (params.as_of).
-- Every bucket is listed, even when empty, so the shape of the backlog is explicit.

WITH buckets(bucket, lo, hi, bucket_order) AS (
    VALUES ('0-30 days', 0, 30, 1),
           ('31-60 days', 31, 60, 2),
           ('61-90 days', 61, 90, 3),
           ('90+ days', 91, 100000, 4)
),
open_reqs AS (
    SELECT r.req_id, date_diff('day', r.opened_at, p.as_of) AS days_open
    FROM dim_requisition AS r
    CROSS JOIN params AS p
    WHERE r.status = 'open'
)
SELECT
    b.bucket,
    COUNT(o.req_id)                 AS open_requisitions,
    ROUND(AVG(o.days_open), 1)      AS avg_days_open
FROM buckets AS b
LEFT JOIN open_reqs AS o
       ON o.days_open BETWEEN b.lo AND b.hi
GROUP BY b.bucket, b.bucket_order
ORDER BY b.bucket_order;
