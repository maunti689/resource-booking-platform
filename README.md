# Платформа бронирования ресурсов

[![CI](https://github.com/maunti689/resource_booking_platform/actions/workflows/ci.yml/badge.svg)](https://github.com/maunti689/resource_booking_platform/actions/workflows/ci.yml)

API для бронирования переговорных, оборудования и других общих ресурсов. Организация задаёт
рабочие часы, ограничения и периоды недоступности, а пользователи ищут свободные слоты,
создают брони и получают напоминания.

![Swagger UI](docs/images/swagger.png)

## Сценарии использования

- офис управляет переговорными и правилами доступа;
- клиника резервирует кабинеты и оборудование;
- коворкинг публикует доступные слоты для участников;
- прокат ведёт календарь ресурсов без пересекающихся выдач.

Одна установка поддерживает несколько изолированных организаций. Роли `admin`, `manager` и
`member` определяют доступ к настройкам, ресурсам, отменам и журналу действий.

## Проблема конкурентного доступа

Проверки свободного интервала недостаточно: два запроса могут одновременно увидеть один
слот доступным. Поэтому создание, перенос, отмена брони и добавление blackout-периода
выполняются внутри `transaction.atomic` и блокируют строку `Resource` через
`SELECT FOR UPDATE`.

После блокировки сервис повторно проверяет пересечения. Для одного ресурса изменения идут
последовательно, а разные ресурсы не мешают друг другу. PostgreSQL-тест открывает два
соединения и подтверждает результат `created + conflict` для пересекающихся запросов.

## Модель данных

- `Organization` хранит timezone и максимальную длительность бронирования.
- `Membership` связывает пользователя с организацией и ролью.
- `Resource` описывает тип, вместимость и состояние ресурса.
- `AvailabilityRule` задаёт недельные рабочие интервалы.
- `BlackoutPeriod` закрывает ресурс на обслуживание или ручную блокировку.
- `Booking` хранит владельца, интервал, статус и причину отмены.
- `BookingParticipant` хранит email приглашённого участника.

Участник не обязан иметь локальную учётную запись: email позволяет включать внешних гостей.
Владение бронью и права на её изменение при этом всегда привязаны к зарегистрированному
пользователю организации.

## API

| Метод и путь | Назначение |
| --- | --- |
| `POST /auth/token` | получить access/refresh JWT |
| `GET, POST /organizations` | список и создание организаций |
| `GET, POST /organizations/{id}/members` | участники и роли |
| `GET, POST /organizations/{id}/resources` | ресурсы организации |
| `GET, POST /organizations/{id}/resources/{id}/availability-rules` | рабочие часы |
| `GET, POST /organizations/{id}/blackouts` | периоды недоступности |
| `GET /organizations/{id}/availability` | поиск свободных слотов |
| `GET, POST /bookings` | список и создание бронирований |
| `POST /bookings/{id}/reschedule` | перенос бронирования |
| `POST /bookings/{id}/cancel` | отмена владельцем или менеджером |
| `POST /bookings/{id}/override-cancel` | административная отмена с причиной |
| `GET /me/schedule` | расписание владельца и участника |
| `GET /organizations/{id}/audit` | журнал действий |

Полные модели запросов и ответов доступны в Swagger UI.

## Запуск

Требуется Docker с поддержкой Compose.

```bash
docker compose up --build -d
docker compose exec api python scripts/seed_demo.py
```

После запуска:

- API: [http://localhost:8000](http://localhost:8000);
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs);
- OpenAPI: [http://localhost:8000/schema](http://localhost:8000/schema);
- readiness: [http://localhost:8000/ready](http://localhost:8000/ready).

| Роль | Логин | Пароль |
| --- | --- | --- |
| Admin | `demo_admin` | `demo-pass` |
| Manager | `demo_manager` | `demo-pass` |
| Member | `demo_member` | `demo-pass` |

```bash
curl -X POST http://localhost:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo_admin","password":"demo-pass"}'
```

Остановка: `docker compose down`. Удаление локальных данных:
`docker compose down -v`.

## Напоминания

Celery Beat каждые пять минут выбирает подтверждённые брони, которые скоро начнутся.
Unique constraint на `(booking, kind)` не допускает повторной доставки одного напоминания.
В этой версии доставка фиксируется в базе и структурированном логе без имитации внешнего
email- или SMS-провайдера.

Redis используется для Celery и короткого кэша расчёта доступности. PostgreSQL остаётся
источником календаря, ролей и истории; сброс кэша не меняет сохранённые бронирования.

## Локальная разработка

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
set -a && source .env && set +a
python manage.py migrate
python scripts/seed_demo.py
uvicorn config.asgi:application --reload
```

При запуске вне Docker в адресах PostgreSQL и Redis нужно заменить имена hosts на
`localhost`. Worker и scheduler запускаются отдельно:

```bash
celery -A config worker --loglevel=INFO
celery -A config beat --loglevel=INFO
```

## Проверки

```bash
ruff format --check .
ruff check .
python manage.py check
python manage.py makemigrations --check --dry-run
pytest --cov --cov-report=term-missing
```

Локальные settings используют SQLite и пропускают тест блокировок PostgreSQL. Полная
проверка конкурентного сценария:

```bash
TEST_DATABASE_URL=postgresql://booking:local-only-booking@localhost:5432/booking_test pytest
```

## Компромиссы версии

- один рабочий интервал на ресурс в каждый день недели;
- бронь должна завершиться в тот же локальный календарный день;
- recurring bookings не реализованы;
- ресурс архивируется вместо физического удаления;
- популярный ресурс последовательно обрабатывает изменения своей строки;
- отдельный пользовательский web-интерфейс не включён.
