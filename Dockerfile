FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir . && \
    useradd --uid 10001 --create-home arbiscope && \
    mkdir -p /data && chown arbiscope:arbiscope /data
USER arbiscope
ENV AS_DB_PATH=/data/arbiscope.sqlite
EXPOSE 8000
CMD ["uvicorn", "arbiscope.api:app", "--host", "0.0.0.0", "--port", "8000"]
