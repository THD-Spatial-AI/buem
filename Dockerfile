FROM continuumio/miniconda3

# install curl for healthcheck
# install system CBC binary so PuLP/cvxpy can call it reliably in container
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl coinor-cbc \
    && rm -rf /var/lib/apt/lists/*

# copy env and create conda env
COPY environment_docker.yml /app/
RUN conda env create -f /app/environment_docker.yml && conda clean -afy

# ensure conda env bin is first on PATH so gunicorn/python are available directly
ENV PATH=/opt/conda/envs/buem_env/bin:$PATH
ENV PYTHONPATH=/app/src

# copy project
COPY . /app

# set work directory
WORKDIR /app/src

EXPOSE 5000

# healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:5000/api/health || exit 1

# run gunicorn directly (uses gunicorn from conda env installed via environment_docker.yml)
CMD gunicorn --bind 0.0.0.0:5000 "buem.apis.api_server:create_app()" --workers "${GUNICORN_WORKERS:-2}" --threads 1