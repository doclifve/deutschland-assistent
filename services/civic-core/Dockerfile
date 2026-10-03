FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DOCUMENT_ENGINE=auto \
    DOCLING_ARTIFACTS_PATH=/opt/docling-models
WORKDIR /app
COPY pyproject.toml ./
COPY deutschland_assistent ./deutschland_assistent
RUN pip install --no-cache-dir '.[docling]'
ARG PREFETCH_DOCLING_MODELS=0
RUN mkdir -p /opt/docling-models && \
    if [ "$PREFETCH_DOCLING_MODELS" = "1" ]; then \
      docling-tools models download -o /opt/docling-models layout tableformer rapidocr \
        --rapidocr-backend-lang onnxruntime:de \
        --rapidocr-backend-lang onnxruntime:en; \
    fi
EXPOSE 8000
CMD ["uvicorn","deutschland_assistent.main:app","--host","0.0.0.0","--port","8000"]
