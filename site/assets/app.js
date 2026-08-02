import { PROJECT, DASHBOARDS } from "./config.js";

const $ = (id) => document.getElementById(id);

/** Wire the project links declared in config.js. */
function applyProjectLinks() {
  const links = [
    ["nav-repo", PROJECT.repo],
    ["cta-repo", PROJECT.repo],
    ["footer-repo", PROJECT.repo],
    ["cta-python", PROJECT.pythonApp],
    ["footer-app", PROJECT.pythonApp],
  ];
  for (const [id, href] of links) {
    const el = $(id);
    if (el) el.href = href;
  }
  $("footer-author").textContent =
    `${PROJECT.name} - ${PROJECT.author} - ${new Date().getFullYear()}`;
}

/**
 * A published viz, or a placeholder when config.js still has src: null.
 * Building the element by hand rather than templating the src into markup keeps
 * an unpublished workbook from rendering as a broken frame.
 */
function buildViz(dash) {
  const frame = document.createElement("div");
  frame.className = "viz-frame";

  if (!dash.src) {
    frame.innerHTML = `
      <div class="viz-placeholder">
        <div>
          <span class="ph-badge">Not published yet</span>
          <h3>${dash.label}</h3>
          <p>Publish the workbook to Tableau Public, then paste its URL into
             the <code>${dash.id}</code> entry in <code>site/assets/config.js</code>.</p>
          <p><code>tableau/BUILD.md</code> has the build steps.</p>
        </div>
      </div>`;
    return frame;
  }

  const scroll = document.createElement("div");
  scroll.className = "viz-scroll";

  const viz = document.createElement("tableau-viz");
  viz.setAttribute("src", dash.src);
  viz.setAttribute("toolbar", "bottom");
  viz.setAttribute("hide-tabs", "");
  viz.setAttribute("width", "100%");
  viz.setAttribute("height", String(dash.height ?? 900));

  scroll.appendChild(viz);
  frame.appendChild(scroll);
  return frame;
}

function buildTabs() {
  const tabs = $("tabs");
  const panels = $("panels");

  DASHBOARDS.forEach((dash, i) => {
    const tab = document.createElement("button");
    tab.className = "tab";
    tab.id = `tab-${dash.id}`;
    tab.type = "button";
    tab.role = "tab";
    tab.textContent = dash.label;
    tab.setAttribute("aria-controls", `panel-${dash.id}`);
    tab.setAttribute("aria-selected", String(i === 0));
    tab.addEventListener("click", () => select(dash.id));
    tabs.appendChild(tab);

    const panel = document.createElement("section");
    panel.className = "panel";
    panel.id = `panel-${dash.id}`;
    panel.role = "tabpanel";
    panel.setAttribute("aria-labelledby", `tab-${dash.id}`);
    panel.hidden = i !== 0;

    const head = document.createElement("div");
    head.className = "panel-head";
    head.innerHTML = `<h2>${dash.question}</h2><p>${dash.blurb}</p>`;

    panel.appendChild(head);
    panel.appendChild(buildViz(dash));
    panels.appendChild(panel);
  });
}

function select(id) {
  for (const dash of DASHBOARDS) {
    const isActive = dash.id === id;
    $(`tab-${dash.id}`).setAttribute("aria-selected", String(isActive));
    $(`panel-${dash.id}`).hidden = !isActive;
  }
}

/** Coverage line, read from the manifest the export writes. Silent if absent. */
async function showCoverage() {
  try {
    const res = await fetch("./data/manifest.json", { cache: "no-cache" });
    if (!res.ok) return;
    const { coverage, tables } = await res.json();
    if (!coverage?.start || !coverage?.end) return;

    const rows = (tables ?? []).reduce((sum, t) => sum + (t.rows ?? 0), 0);
    const fmt = (iso) =>
      new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", {
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      });

    const el = $("coverage");
    el.textContent =
      `Data covers ${fmt(coverage.start)} to ${fmt(coverage.end)}` +
      (rows ? ` - ${rows.toLocaleString("en-US")} rows across ${tables.length} tables` : "");
    el.hidden = false;
  } catch {
    /* manifest is optional - the page is fine without it */
  }
}

applyProjectLinks();
buildTabs();
showCoverage();
