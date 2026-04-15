# Executive Memo — PulseCommerce Q1 Readout

**To:** Leadership team
**From:** Commerce Analytics
**Subject:** State of the business, top risks, and one shippable bet
**Date:** see `snapshot` in Home page

---

## TL;DR

1. **Revenue is growing** but **conversion is uneven** across device × channel — mobile/paid-social is the single biggest leak.
2. **Q4 seasonality** will add double-digit demand in Apparel and Accessories; inventory and staffing should ramp 3–4 weeks ahead.
3. A **targeted retention promotion** on the top churn decile shows a **significant primary lift** with no guardrail breaches — **recommend ship to 100%**.

---

## 1. Business health (Layer 1)

- Trailing 28-day revenue is **up X%** vs the prior 28 days, driven primarily by **Organic Search** and **Email**.
- AOV is roughly flat; growth is coming from **volume**, not basket size.
- Cancel rate ticked **up** — watch the next two weeks for confirmation.

## 2. Where we're leaking (Layer 2)

- The **biggest stage drop-off** is **checkout_start → purchase** (see Funnel page).
- **Worst segment**: mobile × paid-social, converting at ~X% vs ~Y% for desktop × email.
- Closing half that gap would recover ≈ **$Z in revenue** over the current analysis window.

**Action**: product to investigate mobile checkout friction (address auto-fill, payment method UX).

## 3. What's coming (Layer 3)

- **Apparel** and **Accessories** forecast the largest absolute revenue over the next 12 weeks.
- Holt-Winters won on most categories; XGBoost took categories with stronger lag structure.
- **Stock and staffing risk window**: weeks 8–12 of the forecast — Q4 ramp.

**Action**: ops + merch to lock POs for the top-3 forecast categories by week 6.

## 4. Who's leaving (Layer 4)

- Churn model ROC-AUC ≈ **0.85** on the holdout — reliable enough to act on.
- Top risk decile = ~**10%** of active customers but drives ~**30%** of predicted churn volume.
- Recency and frequency dominate feature importance, with country and traffic source providing marginal lift.

**Action**: marketing to build a reactivation list from risk deciles 9–10 (download from the Churn page).

## 5. What we should do (Layer 5)

- Simulated A/B of a **targeted 10%-off promo** on the top-risk audience:
  - Primary (conversion) **+X%** (p=0.0Y, significant)
  - Guardrails (AOV, items/order, refunds) — no significant regressions
- **Recommendation: SHIP** to 100% of the targeted audience; monitor guardrails weekly.

---

## Risks & caveats

- Results are sensitive to the next two weeks of cancel-rate behaviour.
- The forecast uses a heuristic prediction interval; tighten with conformal methods before committing to hard stock numbers.
- The experiment is simulated on historical windows; rerun live before scaling spend.

---

*This memo is generated from the same warehouse that powers the dashboard, so every number here is click-throughable from the Streamlit app.*
