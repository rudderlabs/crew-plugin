# Measuring a lead-scoring Agent

How to tell whether the tiers predict anything, before anyone relies on them.

## Shadow is the baseline

In Shadow the Agent decides on real leads and sends nothing. Every tier is still recorded (Cold
included, because Cold is an action), and the success event still attributes to it. So Shadow gives
each tier's conversion rate with no Crew touch at all: the baseline any later lift is measured
against. Shadow is a 100% holdout; never report delivery or reply rates for it.

## The gate is an outcome test

Agreement with an existing score (a PQL score, a propensity model, the CRM's MQL rule) only shows
the Agent imitates it, and the test turns circular if that score also feeds Intent. Keep any
existing score out of the Agent for the first run and use it only as the baseline.

Agree these with the team before the run starts, and write them down:

| Gate item   | What to agree                                                                                                          |
| ----------- | ---------------------------------------------------------------------------------------------------------------------- |
| Cohort      | Which leads, over how long (two weeks of real signups is a sensible first run)                                         |
| Outcome     | The success event, and the window it must land in (for example 30 days from the decision)                              |
| Baseline    | The existing score on the same people, or the cohort's overall conversion when there is none                           |
| Pass        | Hot converts at a higher rate than the baseline's top band, and few later converters sat in Cold; the exact thresholds |
| Cold review | Someone reads every Cold lead that later converted, to find the reading that got it wrong                              |
| Approver    | Who signs off before the Agent goes Live                                                                               |

The read-out comes after the outcome window closes on the last lead in the cohort, not when the
cohort closes.

## Reading the results

Count people, not decisions. A lead is re-scored on every trigger event, so one person can carry
Cold, then Warm, then Hot, and Crew's own Converted outcome credits only the latest open delivered
sequence per Agent and mode: an earlier Cold decision stays unconverted even when the person
converts, and repeated Hot scores inflate Hot's count.

1. Agree one snapshot rule before the run and use it for every tier, the baseline and the Cold
   review. A sensible one: each person's latest decision inside the cohort window.
2. Pull the cohort's decisions with `analytics_list`: the Agent's id, `mode: "shadow"`,
   `range: "custom"` with `rangeFrom` and `rangeTo` set to the cohort's decision window, and every
   outcome (`delivered`, `no_action`, `blocked`, `failed`, `rate_limited`, `deduplicated`). Without
   a range the list covers only the last seven days, and without `outcomes` the holds are left out.
   Keep the same parameters on every page; `pageSize` must be 25, 50 or 100.
3. Read each decision's chosen option with `analytics_get`, and keep one row per person by the
   snapshot rule.
4. Join conversions by person: did their success event land within the outcome window, counted
   from their snapshot decision? Read the success events from where they are recorded (the
   warehouse or the CRM), not from the Converted outcome.

- A tier mix of mostly Hot means the Fit or Intent wording is too generous; a Cold lead with a
  strong reason to call means a reading is missing a fact. Fix the signal or the option that chose
  it, one change at a time, and rerun the cohort.

## Cost

Lead scoring makes more decisions per lead than a one-message Agent (every trigger event can
re-score), and each research enrichment adds a provider call per person, at most once per TTL and
again when its inputs change. Take the decisions per lead and the enrichment calls from the Shadow
run, and estimate the cost from those before going Live.
