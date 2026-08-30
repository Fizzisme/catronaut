FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8001

# Ollama runs on the host, not in this image. Point the container at it, e.g.
#   docker run -e OLLAMA_BASE_URL=http://host.docker.internal:11434 ...
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
