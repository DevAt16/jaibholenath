FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements-node.txt ./
RUN pip install --no-cache-dir -r requirements-node.txt \
    && useradd --uid 1000 --create-home worker
COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts
COPY migrations ./migrations
COPY data ./data
COPY reports/phase_1_1_district_baseline ./reports/phase_1_1_district_baseline
COPY node ./node
RUN pip install --no-cache-dir --no-deps .
USER 1000:1000
EXPOSE 8787
CMD ["python", "node/control.py"]
