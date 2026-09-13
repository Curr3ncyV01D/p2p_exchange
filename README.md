# 💱 Non-Custodial P2P Exchange Telegram Bot

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Aiogram 3](https://img.shields.io/badge/Aiogram-3.x-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://docs.aiogram.dev)
[![SQLAlchemy 2.0](https://img.shields.io/badge/SQLAlchemy-2.0_Async-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)](https://docs.sqlalchemy.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Alembic](https://img.shields.io/badge/Alembic-Migrations-007ACC?style=for-the-badge)](https://alembic.sqlalchemy.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)

Высоконагруженный некастодиальный P2P-обменник фиатных валют (RUB / KRW / KZT) в Telegram с двусторонней двухфазной верификацией сделки, системой арбитража на базе Telegram Forum Topics и фоновым контролем таймаутов (TTL).

---

## 🌟 Ключевые архитектурные решения

* **Некастодиальная модель (Zero-Custody):** Бот не депонирует средства пользователей, исключая риски блокировок счетов и регуляторные риски. Безопасность обеспечивается репутационной системой, обязательной фиксацией платежных квитанций и арбитражем.
* **Двухфазная модель обмена (Two-Phase Cross-Settlement):** Поддержка полного цикла взаиморасчетов между Тейкером и Мейкером с фиксацией встречных чеков (`buyer_receipt_id` и `seller_receipt_id`).
* **Арбитраж через Telegram Forum Topics:** При открытии спора или заявки на верификацию бот автоматически создает изолированный топик (`group_topic_id`) в супергруппе модераторов, организуя двусторонний мост связи между админами и участниками.
* **Repository Pattern:** Полная изоляция бизнес-логики и хендлеров от SQL-запросов через специализированные репозитории (`user_repo`, `deal_repo`, `ad_repo` и др.).
* **Фоновый TTL-воркер (Deal Timeout Worker):** Асинхронный шедулер (`APScheduler`) для автоматической отмены просроченных этапов сделки (15 мин) и возврата объявлений в маркет.
* **Приватность и безопасность:** Анонимизация пользователей через систему псевдонимов (`pseudonym_service`), встроенные middleware защиты контекста (`deal_guard`, `clean_chat`).

---

## 🏗️ Архитектура системы и жизненный цикл сделки

### 1. Finite State Machine сделки (2-Phase Settlement)

```mermaid
stateDiagram-v2
    [*] --> WAITING_BUYER_PAY: Тейкер принимает заявку
    
    state "Этап 1: Оплата Тейкера" as Phase1 {
        WAITING_BUYER_PAY --> WAITING_SELLER_CONFIRM: Загрузка чека Тейкера
        WAITING_BUYER_PAY --> CANCELLED: Таймаут 15 мин / Отмена
        WAITING_SELLER_CONFIRM --> WAITING_SELLER_PAY: Мейкер подтвердил получение
    }

    state "Этап 2: Оплата Мейкера" as Phase2 {
        WAITING_SELLER_PAY --> WAITING_BUYER_CONFIRM: Загрузка чека Мейкера
        WAITING_SELLER_PAY --> DISPUTED: Таймаут / Ошибка
        WAITING_BUYER_CONFIRM --> COMPLETED: Тейкер подтвердил получение
    }

    WAITING_SELLER_CONFIRM --> DISPUTED: Открытие спора
    WAITING_BUYER_CONFIRM --> DISPUTED: Открытие спора

    COMPLETED --> [*]: Начисление рейтинга и взаимные отзывы
    CANCELLED --> [*]: Возврат объявления в маркет
    DISPUTED --> [*]: Решение арбитража в Forum Topic
```

---

### 2. Схема базы данных (Entity-Relationship)

```mermaid
erDiagram
    User ||--o{ UserRequisite : "has"
    User ||--o{ Ad : "creates"
    User ||--o{ Deal : "participates (buyer/seller)"
    User ||--o| VerificationRequest : "submits"
    User ||--o{ Review : "writes/receives"
    
    Ad ||--o{ Deal : "originates"
    Deal ||--o| Dispute : "can have"
    Deal ||--o{ Review : "evaluated by"

    User {
        bigint id PK "Telegram ID"
        string display_name "Unique Pseudonym"
        float rating "Calculated Rating (1-5)"
        int deal_count
        bool is_verified
        bool is_banned
        int conflict_strikes
    }

    Ad {
        int id PK
        string public_id UK
        enum base_currency "RUB / KRW / KZT"
        enum quote_currency
        float min_limit
        float max_limit
        float rate
        string bank
        enum status "active / pending / hidden / archived"
    }

    Deal {
        int id PK
        string public_id UK
        enum status "FSM Step Status"
        float amount_base
        float amount_quote
        string buyer_receipt_id "Telegram File ID"
        string seller_receipt_id "Telegram File ID"
        datetime expires_at "TTL Deadline"
    }

    Dispute {
        int id PK
        int deal_id FK
        bigint group_topic_id "Admin Forum Topic ID"
        string status "open / closed"
        text reason
    }
```

---

## 📂 Структура проекта

```text
p2p_exchange/
├── migrations/             # Миграции базы данных (Alembic)
├── src/
│   ├── bot/
│   │   ├── handlers/       # Обработчики Telegram (Market, Deals, Dispute, Admin)
│   │   ├── keyboards/      # Inline и Reply клавиатуры
│   │   ├── middlewares/    # Middleware (Auth, DealGuard, CleanChat)
│   │   ├── states/         # Состояния FSM
│   │   └── utils/          # Хелперы UI и форматирования
│   ├── core/
│   │   ├── config.py       # Pydantic Settings конфигурация
│   │   └── constants.py    # Константы системы
│   ├── database/
│   │   ├── models/         # Декларативные модели SQLAlchemy 2.0
│   │   ├── repository/     # Data Access Layer (Repository Pattern)
│   │   └── session.py      # Управление асинхронными сессиями
│   ├── services/           # Бизнес-логика (Шедулер, Воркер таймаутов, Псевдонимы)
│   └── main.py             # Точка входа приложения
├── docker-compose.yml      # Оркестрация сервисов (Bot + PostgreSQL)
├── Dockerfile              # Мультистейдж сборка контейнера
└── requirements.txt        # Зафиксированные зависимости
```

---

## 🚀 Быстрый старт (Deployment)

### 1. Клонирование и настройка переменных окружения

```bash
git clone https://github.com/Curr3ncyV01D/p2p_exchange.git
cd p2p_exchange
cp .env.example .env
```

Заполните `.env` вашими данными:
```env
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/p2p_db
ADMIN_SUPERGROUP_ID=-1001234567890
```

### 2. Запуск через Docker Compose

```bash
docker compose up -d --build
```

Система автоматически применит миграции Alembic, запустит базу данных и активирует фоновые воркеры.

---

## 🛠️ Стек технологий

* **Фреймворк:** `aiogram 3.x` (Asyncio, FSM, Middlewares)
* **База данных:** `PostgreSQL 15+`
* **ORM:** `SQLAlchemy 2.0` (Async Engine, Mapped Columns)
* **Миграции:** `Alembic`
* **Фоновые задачи:** `APScheduler`
* **Контейнеризация:** `Docker`, `Docker Compose`
