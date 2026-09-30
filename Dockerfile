# Offline reproduction of every number in the paper from the archived corpus.
#   docker build -t schemacaps . && docker run --rm schemacaps            (runs `make reproduce`)
# The Coq proof: make proof-docker (coqorg/coq:8.18.0). The client survey needs node and network: make survey.
FROM python:3.11.15-slim
ENV PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends make && rm -rf /var/lib/apt/lists/*
WORKDIR /artefact
COPY requirements.lock ./
RUN pip install -r requirements.lock
COPY . .
CMD ["make", "reproduce"]
