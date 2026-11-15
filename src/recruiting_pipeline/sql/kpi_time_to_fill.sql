-- Time-to-fill (days from opening to closing) for filled requisitions with valid
-- dates, overall and by seniority, area and city. Median and interquartile range,
-- because durations are skewed and a mean would be pulled by a few slow searches.

SELECT
    CASE
        WHEN GROUPING(seniority) = 0 THEN 'seniority'
        WHEN GROUPING(area) = 0      THEN 'area'
        WHEN GROUPING(city) = 0      THEN 'city'
        ELSE 'overall'
    END                                             AS dimension,
    COALESCE(seniority, area, city, 'All')          AS value,
    COUNT(*)                                        AS filled_requisitions,
    MEDIAN(time_to_fill_days)                       AS median_days,
    QUANTILE_CONT(time_to_fill_days, 0.25)          AS p25_days,
    QUANTILE_CONT(time_to_fill_days, 0.75)          AS p75_days
FROM dim_requisition
WHERE ttf_eligible
GROUP BY GROUPING SETS ((seniority), (area), (city), ())
ORDER BY
    CASE dimension WHEN 'overall' THEN 0 WHEN 'seniority' THEN 1 WHEN 'area' THEN 2 ELSE 3 END,
    median_days DESC,
    value;
