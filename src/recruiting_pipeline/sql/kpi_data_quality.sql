-- What the pipeline fixed (WARN) and what it excluded (ERROR), by check.
-- Shown next to the KPIs so every number carries its data-quality context.

SELECT
    table_name,
    check_id,
    severity,
    action,
    COUNT(*) AS affected_rows
FROM dq_log
GROUP BY table_name, check_id, severity, action
ORDER BY CASE severity WHEN 'ERROR' THEN 0 ELSE 1 END, affected_rows DESC, check_id;
