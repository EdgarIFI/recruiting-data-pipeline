# Summary

Snapshot date: 2026-10-12. All data is synthetic.

| KPI | Value |
|---|---:|
| Applications on filled requisitions | 1,546 |
| Applied → interview | 37.1% |
| Applied → hired | 6.9% |
| Median time-to-fill | 41 days (IQR 31–50) |
| Best source by interview rate | Referral 53% (95% CI 46%–59%) |
| Open requisitions older than 90 days | 15 of 42 |

# Objection: does the pipeline change any answer?

Same metrics computed on the raw exports (naive) and on the cleaned, KPI-eligible data (pipeline).

| Metric | Naive | Pipeline | Why it matters |
|---|---:|---:|---|
| Applications counted | 3,037 | 2,955 | Duplicates and untrustworthy rows inflate volume. |
| Distinct source labels | 19 | 6 | Spelling variants split one channel into many. |
| Source labels with < 30 applications | 13 | 0 | Tiny fake 'channels' that no one should rank. |
| Referral applications (filled reqs) | 187 | 194 | Variants such as 'Referido' are lost from the Referral bucket. |
| Referral interview rate (filled reqs) | 52.4% | 52.6% | The planted signal survives; the naive sample is just smaller. |
| Hire rate (filled reqs) | 7.3% | 6.9% | Barely moves: the defects are ~3% of rows. |
| Median time-to-fill, days | 40 | 41 | Medians are robust to a handful of bad dates. |
| Minimum time-to-fill, days | -12 | 17 | Negative durations are impossible; they poison means and minimums. |
| CRM activities linked to an application | 95.1% | 99.3% | Exact-match joins silently drop activities with dirty keys. |

**Reading.** Headline *rates* barely move, because the injected defects touch only a few percent of rows. What the pipeline changes is *structure*: channels are no longer split into spelling variants, impossible durations disappear, and CRM activity is linked to the right candidates. A naive analysis would not be very wrong on averages; it would be wrong on rankings, minimums and joins, and nobody would notice.
