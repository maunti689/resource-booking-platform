# Платформа бронирования ресурсов

Backend-платформа для бронирования переговорных, оборудования и других общих ресурсов в офисе,
коворкинге, клинике или прокате: несколько организаций, роли, рабочие часы, blackout-периоды,
конкурентные бронирования и напоминания.

## Что реализовано

- multi-tenant организации без доступа к данным чужого tenant;
- роли `admin`, `manager`, `member` и проверки прав на уровне сервисов;
- ресурсы с типом, вместимостью, IANA timezone и недельным расписанием;
- поиск свободных слотов с фильтрами по дате, длительности и вместимости;
- создание, перенос, обычная и административная отмена бронирований;
- одна транзакционная проверка правил для создания и переноса;
- защита от гонок через `SELECT FOR UPDATE` на строке ресурса;
- blackout-периоды, кэш доступности с version-based invalidation;
- JWT-аутентификация, единый формат ошибок и request ID;
- audit trail значимых изменений;
- идемпотентные фоновые напоминания через Celery;
- OpenAPI-схема, Swagger UI, health/readiness endpoints;
- миграции, демоданные, Docker Compose и CI.

## Стек

Python 3.12, Django 5, Django REST Framework, PostgreSQL, Redis, Celery, Simple JWT,
drf-spectacular, pytest-django, Ruff, Docker Compose.

Redis используется только там, где есть прикладная причина: короткий кэш расчёта доступности
и транспорт Celery. Источником истины остаётся PostgreSQL.

## Архитектура

```mermaid
flowchart LR
    Client["Swagger / API-клиент"] --> API["Django REST Framework"]
    API --> Services["Сервисный слой"]
    Services --> PostgreSQL[(PostgreSQL)]
    Services --> Redis[("Кэш доступности Redis")]
    Beat["Планировщик Celery"] --> Redis
    Redis --> Worker["Celery worker"]
    Worker --> PostgreSQL
```

HTTP views отвечают за transport и validation, а tenant checks, роли, транзакции и правила
бронирования находятся в service layer. API, worker и scheduler используют одну схему данных.

![Swagger UI](docs/images/swagger.png)

## Ключевые решения

- Один modular monolith вместо искусственных микросервисов: общий booking workflow остаётся
  в одной транзакционной границе.
- Все изменения календаря блокируют строку `Resource`; разные ресурсы не блокируют друг друга.
- Максимальная длительность задаётся для каждой организации, а не глобально для инсталляции.
- Удаление ресурса реализовано как архивирование через `is_active`, чтобы сохранить историю.
- Availability загружается фиксированным числом запросов и кэшируется по версии ресурса.
- Redis не хранит критичное состояние; потеря кэша не влияет на сохранённые бронирования.
- Reminder delivery защищена unique constraint и безопасна при повторном запуске Celery task.

## Быстрый старт

Требуется Docker с поддержкой Compose.

```bash
docker compose up --build -d
docker compose exec api python scripts/seed_demo.py
```

После запуска:

- API: `http://localhost:8000`;
- Swagger UI: `http://localhost:8000/docs`;
- OpenAPI: `http://localhost:8000/schema`;
- readiness: `http://localhost:8000/ready`.

Демопользователи:

| Роль | Логин | Пароль |
| --- | --- | --- |
| Admin | `demo_admin` | `demo-pass` |
| Manager | `demo_manager` | `demo-pass` |
| Member | `demo_member` | `demo-pass` |

Получение JWT:

```bash
curl -X POST http://localhost:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo_admin","password":"demo-pass"}'
```

Остановка окружения:

```bash
docker compose down
```

Удаление локальных данных выполняется отдельно: `docker compose down -v`.

## Основные endpoints

| Метод и путь | Назначение |
| --- | --- |
| `POST /auth/token` | получить access/refresh JWT |
| `GET, POST /organizations` | список и создание организаций |
| `GET, PATCH /organizations/{id}` | настройки организации и лимит длительности |
| `GET, POST /organizations/{id}/members` | участники организации |
| `GET, POST /organizations/{id}/resources` | ресурсы организации |
| `GET, PATCH, DELETE /organizations/{id}/resources/{id}` | ресурс и soft-delete |
| `GET, POST /organizations/{id}/resources/{id}/availability-rules` | рабочие часы |
| `GET, POST /organizations/{id}/blackouts` | периоды недоступности |
| `GET /organizations/{id}/availability` | поиск свободных слотов |
| `GET, POST /bookings` | список и создание бронирований |
| `POST /bookings/{id}/reschedule` | перенос бронирования |
| `POST /bookings/{id}/cancel` | отмена владельцем или менеджером |
| `POST /bookings/{id}/override-cancel` | административная отмена с причиной |
| `GET /me/schedule` | личное расписание владельца и участника |
| `GET /organizations/{id}/audit` | журнал действий для management-ролей |

Точные параметры и модели ответов доступны в Swagger UI.

## Демонстрационный сценарий

1. Получить JWT для `demo_admin`, `demo_manager` и `demo_member`.
2. Проверить организацию с лимитом брони 120 минут и комнату с графиком 09:00–18:00.
3. Создать member-бронирование 12:00–13:00 по timezone комнаты.
4. Отправить пересекающийся запрос вторым пользователем и получить `409 Conflict`.
5. Создать blackout через manager и проверить отсутствие слота в availability search.
6. Выполнить override-cancel с причиной и увидеть событие в audit trail.

## Конкурентные бронирования

Создание бронирования, перенос, отмена и добавление blackout-периода блокируют одну и ту же
строку `Resource` внутри `transaction.atomic`. После получения блокировки сервис повторно
проверяет подтверждённые бронирования и blackout-периоды. Поэтому два одновременных запроса
на пересекающееся время не могут успешно записаться вместе.

Блокировка локальна для одного ресурса: бронирования разных комнат не мешают друг другу.
PostgreSQL integration-тест запускает два запроса из отдельных соединений и проверяет, что
один создаёт запись, а второй получает `409 Conflict`.

Подробные решения и ограничения описаны в `docs/architecture.md`.

## Напоминания

Celery Beat каждые пять минут выбирает подтверждённые бронирования, которые начнутся в
настраиваемом интервале `BOOKING_REMINDER_LEAD_MINUTES`. Уникальность `(booking, kind)`
делает повторную обработку безопасной. В MVP
доставка фиксируется в базе и структурированном логе; интеграция с конкретным email/SMS
провайдером намеренно не имитируется.

## Локальная разработка

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
set -a && source .env && set +a
```

Для обычного запуска нужны PostgreSQL и Redis. Переменные окружения перечислены в
`.env.example`; при запуске процессов вне Docker замените имена hosts `postgres` и `redis`
на `localhost`. Схема меняется только миграциями:

```bash
python manage.py migrate
python scripts/seed_demo.py
uvicorn config.asgi:application --reload
```

Worker и scheduler запускаются отдельными процессами:

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

Локальный test settings использует SQLite и пропускает тест PostgreSQL row locking. Полная
проверка, включая конкурентный сценарий, выполняется так:

```bash
TEST_DATABASE_URL=postgresql://booking:local-only-booking@localhost:5432/booking_test pytest
```

CI запускает проверки на PostgreSQL 17 и Redis 7. Текущее локальное покрытие — более 90%.

## Структура

- `apps/organizations/` — организации, memberships и роли;
- `apps/resources/` — ресурсы, рабочие часы, blackout и поиск слотов;
- `apps/bookings/` — бронирования, участники и reminders;
- `apps/audit/` — история значимых действий;
- `config/` — Django, Celery, логирование и API errors;
- `tests/` — unit, integration, e2e и PostgreSQL concurrency tests;
- `docker/`, `scripts/`, `docs/` — запуск, демоданные и инженерные решения.

## Осознанные ограничения MVP

- одно окно доступности на ресурс в каждый день недели;
- бронирование должно завершиться в тот же локальный календарный день;
- нет recurring bookings и физического удаления ресурсов с историей;
- нет внешнего провайдера уведомлений и пользовательского web-интерфейса;
- горячий ресурс сериализует изменения одной строковой блокировкой.

Ограничения не затрагивают критичные части системы: tenant isolation, permissions, транзакции,
гонки и идемпотентность.
