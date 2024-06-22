compose = docker compose -f docker/docker-compose.yml

build-docker:
	$(compose) up -d --build

build:
	python3 -m venv .venv \
	&& ./.venv/bin/pip install poetry \
	&& poetry config virtualenvs.create false \
	&& poetry install --no-interaction \
