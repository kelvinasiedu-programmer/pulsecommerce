FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# HF Spaces runs as non-root user "user" with UID 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

COPY --chown=user requirements.txt ./
RUN pip install --user -r requirements.txt

COPY --chown=user pyproject.toml README.md ./
COPY --chown=user src ./src
COPY --chown=user sql ./sql
COPY --chown=user dashboard ./dashboard
COPY --chown=user scripts ./scripts

RUN pip install --user -e .

# Bake a small dataset + warehouse so the app boots instantly on HF.
RUN python -m pulsecommerce.cli generate --seed 42 --small \
    && python -m pulsecommerce.cli warehouse \
    && python -m pulsecommerce.cli pipeline

EXPOSE 7860

CMD ["streamlit", "run", "dashboard/Home.py", \
     "--server.port=7860", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
