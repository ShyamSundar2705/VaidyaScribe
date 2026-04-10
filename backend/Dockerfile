FROM python:3.12-slim

# Build context is project root (context: .)
# backend/ source lands at /app/backend/
# We set WORKDIR to /app/backend so "app.main" resolves correctly

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ffmpeg libsndfile1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# Copy requirements first for layer caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy medical NER model
RUN pip install --no-cache-dir \
    https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_md-0.5.4.tar.gz

# Copy all backend source
COPY backend/ .

RUN mkdir -p data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
