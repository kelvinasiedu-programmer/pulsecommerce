/**
 * Tableau Public workbook wiring.
 *
 * After publishing a workbook, open it on Tableau Public, click Share, and copy
 * the link. Strip everything from "?" onward and paste the result into `src`.
 * A URL still set to null renders a "not published yet" card instead of a
 * broken embed, so the site is safe to deploy before the workbooks exist.
 *
 * Shape of a published URL:
 *   https://public.tableau.com/views/<WorkbookName>/<SheetName>
 */

export const PROJECT = {
  name: "PulseCommerce",
  tagline: "Ecommerce analytics on a synthetic 25k-customer dataset.",
  repo: "https://github.com/kelvinasiedu-programmer/pulsecommerce",
  pythonApp: "https://kelvin-programmer-pulsecommerce.hf.space",
  author: "Kelvin Asiedu",
};

export const DASHBOARDS = [
  {
    id: "health",
    label: "Business Health",
    question: "Is the business healthy?",
    blurb:
      "Revenue, margin, AOV and conversion against the prior period, with channel " +
      "and category mix underneath. Cancelled and returned orders are filtered out " +
      "at the data source, so every number matches the KPI dictionary.",
    src: "https://public.tableau.com/views/PulseCommerce-Business-Health/BusinessHealth",
    height: 920,
  },
  {
    id: "funnel",
    label: "Funnel Drop-Off",
    question: "Where do we lose customers?",
    blurb:
      "A five-stage session funnel from first visit to purchase, split by device " +
      "and channel. The heatmap ranks 21 device-channel segments by end-to-end " +
      "conversion so the worst performers surface without hunting.",
    src: "https://public.tableau.com/views/PulseCommerce-FunnelDrop-Off/FunnelDrop-Off",
    height: 900,
  },
  {
    id: "cohorts",
    label: "Cohort Retention",
    question: "Do customers come back?",
    blurb:
      "Monthly acquisition cohorts tracked across their first 26 months. The " +
      "triangle reads down for cohort quality and across for decay, which is the " +
      "fastest way to see whether retention is improving or the cohorts just got " +
      "bigger.",
    src: "https://public.tableau.com/views/PulseCommerce-CohortRetention/CohortRetention",
    height: 1170,
  },
];
