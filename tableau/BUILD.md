# Building the Tableau Public workbooks

Three workbooks, published separately so each gets its own URL and the site can
embed them independently. Budget about 40 minutes for the first one and 20 each
for the other two.

Everything here targets **Tableau Desktop Public Edition 2025.2**.

## Before you start

```bash
python -m pulsecommerce.cli all      # full dataset + warehouse + 5 layers
python -m pulsecommerce.cli tableau  # writes data/tableau/*.csv
```

That produces:

| File | Rows | Feeds |
|---|---|---|
| `kpi_daily.csv` | ~820 | Business Health trend + KPI tiles |
| `orders_fact.csv` | ~257k | Business Health mix breakdowns |
| `funnel_stages.csv` | ~12k | Funnel bars |
| `funnel_segments.csv` | 21 | Funnel segment heatmap |
| `cohort_retention.csv` | 378 | Cohort triangle |
| `manifest.json` | - | Row counts and date coverage, copied to `site/data/` |

Tableau Public workbooks must have their data extracted into the workbook, not
linked to your local disk. Every connection below is a **text file** connection,
and the publish step embeds the data automatically.

---

## Workbook 1: Business Health

**Connect.** Open Tableau Public, Connect > Text File > `kpi_daily.csv`. Then in
the Data Source tab, add a second connection to `orders_fact.csv` (Add > Text
File). Leave them as separate data sources - do not join them. They are at
different grains and joining them will double-count revenue.

**Data source filter (do this first).** On the `orders_fact` data source, top
right > Filters > Add > `Status Group` > select `net_sale` only. This is what
makes Tableau agree with `docs/kpi_dictionary.md`, which excludes cancelled and
returned orders from revenue, margin and order counts. Skip it and every number
on the dashboard will be about 12% too high.

**Calculations** on `kpi_daily`:

```
// AOV
SUM([Revenue]) / SUM([Orders])

// Conversion Rate
SUM([Purchase Sessions]) / SUM([Sessions])

// Margin Rate
SUM([Margin]) / SUM([Revenue])

// Revenue vs prior period  (table calc, use on the KPI tiles)
(SUM([Revenue]) - LOOKUP(SUM([Revenue]), -1)) / ABS(LOOKUP(SUM([Revenue]), -1))
```

**Sheets:**

1. `KPI Tiles` - Rows: Measure Names, filtered to Revenue, Margin, Orders,
   Sessions, AOV, Conversion Rate. Marks: Text. Format as currency / percent to
   match the KPI dictionary.
2. `Revenue Trend` - `Metric Date` (continuous, week) on Columns, `SUM(Revenue)`
   on Rows. Add a second measure `SUM(Margin)` as a dual axis, synchronised.
   Add a 4-week moving average trend line.
3. `Channel Mix` - `Channel` on Rows sorted by revenue descending,
   `SUM(Revenue)` on Columns, `AOV` on Color.
4. `Category Mix` - `Category` on Rows, `SUM(Revenue)` on Columns, `Margin Rate`
   on Color using a sequential blue ramp.

**Dashboard** `Business Health`, size Fixed 1200 x 900:
KPI Tiles across the top, Revenue Trend below it full width, then Channel Mix
and Category Mix side by side. Add a `Metric Date` range filter and a `Device`
filter, both applied to all sheets using this data source.

---

## Workbook 2: Funnel Drop-Off

**Connect** to `funnel_stages.csv` and, as a second data source,
`funnel_segments.csv`.

`funnel_stages` is already in long format - one row per week, device, channel
and stage - so the funnel is a plain bar chart. `Stage Order` exists purely to
sort the stages correctly; sorting on `Stage` alphabetically gives you
"Add to Cart, Checkout Start, Product View..." which is nonsense.

**Calculations** on `funnel_stages`:

```
// Step Conversion - share of the previous stage that made it through
SUM([Sessions Reached]) / LOOKUP(SUM([Sessions Reached]), -1)

// Share of Top - share of all sessions that reached this stage
SUM([Sessions Reached]) / TOTAL(SUM([Sessions Reached]))
```

For `Step Conversion`, set Compute Using to `Stage` so it walks down the funnel.

**Sheets:**

1. `Funnel` - `Stage` on Rows sorted by `Stage Order` ascending,
   `SUM(Sessions Reached)` on Columns. Put `Step Conversion` on Label. Sort
   descending by stage order so it reads top to bottom.
2. `Segment Heatmap` - from `funnel_segments`: `Device` on Columns, `Channel` on
   Rows, `Overall Conversion` on Color (diverging red to green), and again on
   Label. 21 marks, no aggregation needed.
3. `Stage Rates by Device` - `Stage` on Columns, `Step Conversion` on Rows,
   `Device` on Color. Shows where mobile diverges from desktop.

**Dashboard** `Funnel Drop-Off`, Fixed 1200 x 880: Funnel on the left, Segment
Heatmap top right, Stage Rates bottom right. Add `Week Start` range and
`Channel` filters.

Set the Segment Heatmap as a filter source (Use as Filter) so clicking a cell
drills the funnel into that segment. That interaction is the reason this is
worth doing in Tableau rather than shipping a picture.

---

## Workbook 3: Cohort Retention

**Connect** to `cohort_retention.csv`.

**Calculation:**

```
// Cohort Label - keeps the axis readable
DATENAME('month', [Cohort Month]) + " " + STR(YEAR([Cohort Month]))
```

**Sheets:**

1. `Retention Triangle` - `Month Number` (discrete) on Columns, `Cohort Month`
   (discrete, month/year) on Rows descending, `Retention Rate` on Color and
   Label. Marks: Square. Color: sequential blue, and **fix the range 0 to 0.5**.
   Leaving it automatic lets month 0 (always 100%) flatten every other cell to
   the same pale shade.
2. `Retention Curve` - `Month Number` on Columns, `AVG(Retention Rate)` on Rows,
   one line. Add `Cohort Month` on Detail with low opacity to show the spread
   behind the average.
3. `Cohort Sizes` - `Cohort Month` on Columns, `MAX(Cohort Size)` on Rows as
   bars. Use MAX, not SUM - cohort size is repeated on every row of the cohort
   and SUM will multiply it by the number of months.

**Dashboard** `Cohort Retention`, Fixed 1200 x 800: Cohort Sizes as a short
strip on top, Retention Triangle in the middle, Retention Curve at the bottom.

Filter `Month Number <= 24` so the sparse tail of the youngest cohorts does not
stretch the axis.

---

## Publishing

For each workbook: File > Save to Tableau Public As, sign in, name it
`PulseCommerce - Business Health` (and so on).

Then on each published viz, uncheck **Show Sheets as Tabs** in the Tableau Public
web editor, otherwise the embed shows a tab strip that duplicates the site's own
navigation.

Copy each URL and strip the query string:

```
https://public.tableau.com/views/PulseCommerceBusinessHealth/BusinessHealth?:language=en-US&...
                                                                            ^ cut from here
```

Paste the three results into `site/assets/config.js`:

```js
{ id: "health",  ..., src: "https://public.tableau.com/views/PulseCommerceBusinessHealth/BusinessHealth" },
{ id: "funnel",  ..., src: "https://public.tableau.com/views/PulseCommerceFunnelDropOff/FunnelDropOff" },
{ id: "cohorts", ..., src: "https://public.tableau.com/views/PulseCommerceCohortRetention/CohortRetention" },
```

Until a `src` is filled in, the site renders a "not published yet" card in that
tab rather than a broken frame, so it is safe to deploy the site first.

## Refreshing later

Re-run `python -m pulsecommerce.cli all && python -m pulsecommerce.cli tableau`,
then in each workbook use Data > Refresh from the source CSV and re-publish.
Tableau Public has no scheduled refresh - the data is embedded at publish time.

## Two things that will bite you

**Tableau Public is public.** Anything you publish is world-readable and
downloadable, including the underlying extract. That is fine here because the
data is synthetic, but do not develop the habit on real work.

**Row limit.** Tableau Public caps a data source at 15 million rows.
`orders_fact.csv` is about 257k, so there is plenty of headroom, but if you ever
raise `n_orders` in `DataGenConfig` keep an eye on it.
