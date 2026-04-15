# Deployment Runbook

Three supported targets. Pick the one that matches the audience.

## 1. Streamlit Community Cloud (free, public)

**Best for**: resumes, portfolio links, recruiter demos.

1. Push the repo to GitHub.
2. Visit [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Configure:
   - Repository: `kelvinasiedu/pulsecommerce`
   - Branch: `main`
   - Main file path: `dashboard/Home.py`
   - Python version: `3.12`
4. Click **Deploy**. Streamlit Cloud installs `requirements.txt` automatically.

> **Cold-start bootstrap.** The cloud container starts empty. Two options:
>
> - **Option A (small dataset, instant)**: commit `data/processed/*.parquet` and `data/processed/*.json` generated with `pulsecommerce all --small`. Dashboard boots in ~2 s.
> - **Option B (full dataset, one-time warmup)**: add the following snippet at the top of `dashboard/Home.py`:
>
>   ```python
>   from pulsecommerce.config import WAREHOUSE_PATH
>   if not WAREHOUSE_PATH.exists():
>       import streamlit as st
>       with st.spinner("First boot — building warehouse (~60 s)…"):
>           from pulsecommerce.cli import main
>           main(["all", "--small"])
>   ```

## 2. Docker (any host)

```bash
docker build -t pulsecommerce:latest .
docker run --rm -p 8501:8501 pulsecommerce:latest
# open http://localhost:8501
```

The image bakes in the dataset and warehouse on build, so the container boots instantly.

### Push to a registry

```bash
docker tag pulsecommerce:latest ghcr.io/kelvinasiedu/pulsecommerce:latest
docker push ghcr.io/kelvinasiedu/pulsecommerce:latest
```

## 3. Cloud Run / Fly.io / Railway (production-ish)

Use the Dockerfile as-is. Two adjustments for managed platforms:

- **Port**: most platforms inject `PORT`. Start command becomes:
  ```bash
  streamlit run dashboard/Home.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true
  ```
- **Persistence**: the warehouse is built into the image, so the container is stateless. If you want live refresh, mount a volume at `/app/data/warehouse` and schedule `pulsecommerce all` as a daily job.

## 4. GitHub Actions as a data-refresh job

`.github/workflows/refresh.yml` (template):

```yaml
name: Nightly refresh
on:
  schedule:
    - cron: "0 5 * * *"
jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt && pip install -e .
      - run: python -m pulsecommerce.cli all --small
      - uses: actions/upload-artifact@v4
        with: { name: warehouse, path: data/ }
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No data found` banner on Home | Run `python -m pulsecommerce.cli all` before launching Streamlit |
| `FileNotFoundError: .../users.parquet` | Same as above |
| Streamlit port in use | `streamlit run dashboard/Home.py --server.port=8502` |
| DuckDB lock | Kill other processes touching `data/warehouse/pulse.duckdb` or delete and rebuild |
