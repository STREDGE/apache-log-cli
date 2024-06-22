# Apache CLI Log Reader

## Dependencies

- Docker
- Python >= 3.11

## Build

```shell
make build-docker
make build
```

## Run CLI (with Docker)

```shell
docker compose -f docker/docker-compose.yml run cli --help
```

## Run CLI (without Docker)

```shell
# после активации виртуального окружения
python -m src --help
```

## Example

```
# необязательно указывать и старт, и конец. можно один из параметров
python -m src get_log by-date --start 2024-06-01 --end '2024-06-05 18:00:00'

python -m src get_log by-ip 92.123.149.183
# на каждую команду есть документация (--help)
```

Докер собирает базу данных, apache и запускает крон для сбора логов. `config/config.toml` содержит ссылку для подключения к бд и ссылку к бд для крона, которые необязательно менять (там данные от докер контейнера с бд), а также путь к логам, которые отправляются из контейнера apache в контейнер с кроном (тоже необязательно менять). Apache-сервер доступен по адресу <http://localhost:8080>.
