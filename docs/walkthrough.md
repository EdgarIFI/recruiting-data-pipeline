# Project walkthrough and FAQ

*Español: [walkthrough.es.md](walkthrough.es.md)*

A short spoken overview of this project, followed by the questions people usually ask about it: first the general ones, then the technical ones from a senior data-analytics reviewer. All figures refer to the default run (seed 2027) on **synthetic data**.

---

## The 90-second overview

> In my data-intelligence internship I run a weekly pipeline that reconciles about 3,400 wellbeing alerts with 1,700 CRM cases before they reach a dashboard. The hard part is not the dashboard; it is making sure the numbers underneath can be trusted. That work is confidential, so I rebuilt the method from scratch, in public, on a recruiting funnel.
>
> Three systems describe the same candidates and disagree in nine ways: duplicates, spelling variants, broken keys, impossible dates. The pipeline identifies each file by its content, validates it in two layers (pandera for schemas, hand-written rules for business logic), fixes what can be fixed deterministically, and keeps out of the KPIs what cannot be trusted. Then it builds a DuckDB model and computes the KPIs in SQL.
>
> What I care most about is how it is tested. I plant defects with a known count, and the validation has to find exactly that many, for any seed, and zero on clean data. The analysis reports 95% intervals and has an objection step where I try to break my own conclusions. For example, cleaning barely moves the average hire rate, but a naive analysis would see 19 sourcing channels instead of 6 and a negative time-to-fill.
>
> It is Python and SQL, with 71 tests running in CI.

**Shorter version (30 seconds):** *A recruiting-funnel pipeline that validates data before it computes KPIs. Every data-quality check is tested against defects planted with a known count: it finds 9 of 9 exactly and nothing on clean data. KPIs are in SQL, cross-checked in pandas, reported with confidence intervals, and challenged by an objection step.*

---

## Part 1 · General questions (recruiters, HR, hiring teams)

**1. What is this project, in one minute?**
A pipeline that takes recruiting data from three systems that disagree, proves it is trustworthy, and only then computes hiring-funnel KPIs. The proof is that every data-quality check finds exactly the defects that were planted on purpose, and nothing on clean data.

**2. Why did you build it?**
My internship work does the same thing with confidential data, so I can't show it. I wanted public, inspectable evidence of the method. I chose recruiting because everyone understands a hiring funnel.

**3. Is the data real?**
No, it is synthetic, generated with a fixed seed. That is a feature: because I know exactly which defects and effects I planted, I can check that the pipeline finds them. Every findings slide and section says the data is synthetic.

**4. What was the hardest part?**
Deciding what "trustworthy" means in practice: which problems can be fixed automatically (WARN) and which mean the row cannot be used (ERROR). The second hardest part was making the synthetic data realistic. Reviewing my own generator, I found four inconsistencies, such as hires on cancelled requisitions, and fixed them before trusting any result.

**5. Which tools did you use?**
Python and SQL first: pandas, pandera for validation, DuckDB for the SQL model and KPIs, pytest for 71 tests, and GitHub Actions to run them automatically. The figures use matplotlib; the case-study deck is in PowerPoint.

**6. What did you learn?**
Three things. Validation is only as good as its tests. Averages hide structural errors: a naive analysis gets the average hire rate almost right but the rankings and joins wrong. And a result without its uncertainty invites the wrong decision.

**7. How did you organize the work?**
In two reviewed milestones, each one a pull request: first ingestion and validation, then the model, KPIs and report. Then the write-up and the deck. Every change went through continuous integration before it was merged.

**8. Did you use AI tools?**
Yes, Claude, for code and documentation, and the repository says so. I framed the problem, made the design decisions, reviewed every change before merging it, and validated the results. I can explain every decision in it, which is the standard I hold myself to.

**9. How does this relate to the role?**
Most analytics roles need three things this project shows: making data trustworthy before reporting on it, writing and checking SQL, and explaining results, including their uncertainty, to people who will act on them.

**10. What would you do next?**
An interactive layer in Power BI on the exported model; fuzzy matching for duplicate candidates; and scheduled runs that alert when data-quality counts jump.

---

## Part 2 · Technical questions (senior data-analytics reviewer)

**1. You recovered effects you planted yourself. Isn't that circular?**
For the *findings*, yes, and I say so: the numbers describe the generator, not any company. The planted signals test the *method*. They check that the analysis detects a real effect (referrals, seniority) and does not invent one where none exists (the other five sources). It is a test of sensitivity and specificity, not evidence about the world. With real data I would validate against a holdout period or an external benchmark.

**2. Why pandera plus hand-written rules, and not Great Expectations or dbt tests?**
Scale and readability. pandera is lightweight and declarative for column-level checks. Cross-table rules (an application before its requisition opened) are clearer as explicit code that a reviewer can challenge. The rules are boolean masks shared by validation and cleaning, so the data-quality log matches the report by construction. In a warehouse with orchestration, I would move them to dbt tests or Great Expectations.

**3. Why DuckDB?**
In-process analytical SQL with zero infrastructure, so anyone can reproduce the run with one command. The SQL is standard (window functions, `GROUPING SETS`, `FILTER`) and would port to Postgres or Snowflake with minor changes. The KPIs live in plain `.sql` files, not strings inside Python.

**4. How do you know the SQL is right?**
Three ways. The main KPIs are recomputed independently in pandas and must match. The Wilson intervals are checked against the closed-form formula. And consistency checks hold: aging buckets and recruiter load both account for every open requisition, and no event falls after the snapshot date.

**5. Why Wilson intervals? And is "no overlap" a proper test?**
With a few hundred applications per source and rates sometimes near 0, the normal approximation behaves badly; Wilson keeps good coverage and has a closed form. Non-overlapping 95% intervals are a *conservative* signal of a difference, and overlapping intervals do not prove there is none. A formal version would be pairwise two-proportion tests with a Holm correction. To rank sources fairly, I would use a beta-binomial model that shrinks small samples toward the mean.

**6. Your time-to-fill uses filled requisitions only. Isn't it biased?**
Yes: it is right-censored. The 15 requisitions open for more than 90 days are exactly the slow ones, and they are not in the median, so the reported 41 days is optimistic. The right next step is survival analysis (Kaplan–Meier, with open requisitions as censored observations). I list this as a limitation rather than hide it.

**7. How do you define the funnel, and what breaks that definition?**
Each application counts at every stage up to the furthest one it reached, which assumes a monotone funnel. It breaks with skipped stages that are recorded inconsistently, and with candidates who apply to several requisitions: the grain is the application, not the person. A candidate-level funnel would need entity resolution first.

**8. How would you take this to production?**
Snapshot date as a parameter and incremental loads; orchestration (Airflow, Prefect or dbt); a data contract with each source owner; and the data-quality log stored over time, with alerts when WARN or ERROR counts jump. The schema-drift check already shows the value: one export in six changed format.

**9. A stakeholder says excluding ERROR rows hides real candidates. What do you answer?**
Nothing is deleted except exact duplicates. ERROR rows are flagged and listed in a log with sample IDs, so they can be fixed at the source. The objection step shows how much each choice moves the result: here, the rates barely move. If the business wants a different threshold, the decision is explicit and its impact is visible.

**10. What is the weakest part of this project?**
The data is synthetic, so the findings are only as realistic as the generator. Beyond that: no fuzzy matching for duplicate people, time-to-fill is censored, and per-source hire rates are noisy because hires are capped by openings. I would rather list these myself than have a reviewer find them.
