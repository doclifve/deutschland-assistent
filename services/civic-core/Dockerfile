FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY deutschland_assistent ./deutschland_assistent
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn","deutschland_assistent.main:app","--host","0.0.0.0","--port","8000"]
