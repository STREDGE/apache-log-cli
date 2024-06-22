FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml poetry.lock /app

RUN python3 -m pip install --upgrade pip && python3 -m pip install poetry
RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction

COPY src /app/src
COPY config /app/config
