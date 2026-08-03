# PulseCommerce site

Static front door for the project. Embeds the three Tableau Public workbooks and
links out to the Python app and the source.

No build step, no dependencies. Three files do the work:

```
site/
├── index.html            page structure
├── assets/config.js      workbook URLs and copy   <- the only file you edit routinely
├── assets/app.js         tab switching + embeds
├── assets/styles.css     palette mirrors dashboard/theme.py
└── data/manifest.json    written by `pulsecommerce tableau`
```

## Why this exists

A Hugging Face Space on free hardware sleeps after a period without traffic. A
recruiter opening the link cold waits through a container start, or sees an
error. This page is static, so it loads immediately whenever anyone opens it,
and the Streamlit app becomes the thing you click through to rather than the
first impression.

## Local preview

Needs a real HTTP server - `app.js` and `config.js` are ES modules, and browsers
block module imports over `file://`.

```bash
python -m http.server 8000 --directory site
```

Then open <http://localhost:8000>.

## Deploy

**Vercel** (matches how the portfolio site is already deployed):

1. New Project, import the `pulsecommerce` repo.
2. Framework Preset: **Other**.
3. **Root Directory: `site`**. This is the only setting that matters - point it
   at the repo root and you get a directory listing instead of the page.
4. Deploy. `site/vercel.json` handles the rest.

**GitHub Pages** as an alternative: Settings > Pages > deploy from branch
`main`, folder `/site`.

## After publishing a workbook

Paste its URL into the matching entry in `assets/config.js`. Any entry still set
to `src: null` renders a "not published yet" card, so partial progress deploys
cleanly. `tableau/BUILD.md` covers the Tableau side.
