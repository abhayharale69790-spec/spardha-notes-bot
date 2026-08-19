# Production Telegram Study Platform & Automated Document Distribution Engine 📚⚡

A hardened, enterprise-ready asynchronous Telegram Bot and Web Scraping / Document Distribution engine built for competitive exam students (MPSC, Saral Seva, Police Bharti, Banking).

---

## 🌟 Production Upgrades & Key Architecture

```mermaid
flowchart TD
    subgraph Scraper & Ingestion Layer
        Watcher[Portal Watcher Cron] -->|Domain Rate Limited Requests| ResilientClient[Resilient HTTP Client\n(Tenacity + SSL Bypass + UA Rotation)]
        ResilientClient -->|Scrapes MPSC, MahaGR, Police Bharti, Saral Seva| Parser[Parser & 3-Point Bilingual Summary Generator]
        Parser -->|Check if URL exists| DB[(PostgreSQL 16 / Fallback SQLite)]
        Parser -->|Draft Post| StagingSender[Staging Channel Sender]
    end

    subgraph Admin Moderation Channel
        StagingSender -->|Post Draft with Action Buttons| StagingChannel[Admin Staging Channel]
        AdminUser[Admin Moderator] -->|Approve / Discard| AuthMiddleware[Admin Auth Filter]
        AuthMiddleware -->|Broadcast via Rate-Limited Queue| BroadcastQueue[Broadcast Queue\n(Leaky Bucket)]
        BroadcastQueue -->|Post Document| MainChannel[Main Public Broadcast Channel]
        AuthMiddleware -->|Cache telegram_file_id & Update Status| DB
    end

    subgraph Student Bot Interface
        Student[Aspirant / Student] -->|Commands & Queries| ThrottlingMiddleware[Throttling Middleware\n(Leaky Bucket Rate Limiter)]
        ThrottlingMiddleware -->|/start, Navigation| MenuHandler[Categories & Navigation Handler]
        ThrottlingMiddleware -->|/search query or @bot inline| FuzzySearch[RapidFuzz Bilingual Search\n(English & Marathi)]
        FuzzySearch -->|Match Materials| DB
        MenuHandler -->|Direct Dispatch using telegram_file_id| Student
    end

    subgraph Disaster Recovery
        BackupWorker[Daily Backup Cron] -->|Automated DB Snapshot| TelegramBackup[Telegram Backup Channel\n(Timestamped DB Archive)]
    end
```

### 🛡️ Production Hardening Features:
1. **Resilient HTTP Engine (`scraper/client.py`)**:
   - `tenacity` exponential backoff retries for network timeouts and HTTP 5xx errors.
   - User-Agent header rotation across modern desktop browsers.
   - Transparent `verify=False` fallback for government portals with expired or invalid SSL chains.
   - Domain-level rate pacing (2.0s interval) to prevent WAF / firewall bans.
2. **RapidFuzz Bilingual Search (`database/crud.py`)**:
   - Matches English and Marathi transliterations (e.g., `Rajyashastra` ↔ `राज्यशास्त्र` ↔ `Polity`, `Itihas` ↔ `इतिहास` ↔ `History`).
   - Fuzzy typo tolerance with `token_set_ratio` ranking.
3. **Telegram Anti-Flood & Rate Limiting (`bot/middlewares/throttling.py`)**:
   - Leaky-bucket rate limiter per user to prevent bot ban or command flooding.
   - Graceful handling of Telegram `RetryAfter` (HTTP 429) errors without terminating the bot process.
   - Strict admin-only access control on staging approval actions (`bot/middlewares/auth.py`).
4. **Automated Disaster Recovery Backups (`workers/backup_worker.py`)**:
   - Scheduled automated daily database exports (compressed `.sql.gz` or `.sqlite.gz`).
   - Uploads backups directly to `BACKUP_CHANNEL_ID` with SHA-256 integrity checksums.
5. **Zero-Bandwidth File Distribution**:
   - Caches Telegram's `telegram_file_id` on first broadcast or send, serving subsequent student requests in milliseconds without re-uploading large PDF binaries.

---

## 📁 Directory Structure

```text
telegram_study_platform/
├── config/
│   ├── __init__.py
│   └── settings.py              # Pydantic-settings v2 with full validation
├── database/
│   ├── __init__.py
│   ├── models.py                # SQLAlchemy 2.0 async models with indexing
│   ├── session.py               # Async engine (PostgreSQL/asyncpg + fallback SQLite)
│   └── crud.py                  # CRUD operations with RapidFuzz bilingual search
├── bot/
│   ├── __init__.py
│   ├── bot_instance.py          # Bot initialization with HTML parse mode & router wiring
│   ├── middlewares/
│   │   ├── __init__.py
│   │   ├── throttling.py        # Aiogram 3 leaky-bucket rate limiting & retry middleware
│   │   └── auth.py              # Strict admin authentication filter & middleware
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py             # Welcome & main navigation
│   │   ├── search.py            # RapidFuzz search & Telegram inline mode query
│   │   ├── categories.py        # Drill-down menus (Exam -> Subject -> Year)
│   │   └── admin_staging.py     # Approval callbacks with file_id capture & broadcast
│   └── keyboards/
│       ├── __init__.py
│       └── inline_menus.py      # Dynamic inline button builders & callback factories
├── scraper/
│   ├── __init__.py
│   ├── client.py                # Resilient HTTP client with retry, UA rotation, and SSL bypass
│   ├── portal_watcher.py        # Scrapers for MPSC, MahaGR, Police Bharti, and Saral Seva
│   └── staging_sender.py        # Formats and posts drafts to Admin Staging
├── workers/
│   ├── __init__.py
│   ├── backup_worker.py         # Daily automated DB dump uploaded to Private Telegram Channel
│   └── broadcast_queue.py       # Rate-limited broadcasting worker (leaky bucket algorithm)
├── tests/
│   ├── __init__.py
│   ├── test_database.py         # Database models & CRUD operations tests
│   ├── test_scraper.py          # Scraper resilience & summary tests
│   └── test_search.py           # RapidFuzz bilingual & typo matching tests
├── main.py                      # Multi-task async runner (Bot + Scraper + Backup Cron)
├── requirements.txt             # Locked production dependencies
├── .env.example                 # Environment configuration template
├── Dockerfile                   # Multi-stage ARM64 & x86_64 production build
├── docker-compose.yml           # PostgreSQL 16 + Redis + Bot Application
├── deploy/
│   └── studybot.service         # systemd unit file with automatic crash recovery
└── README.md                    # Setup and operations guide
```

---

## ⚙️ Environment Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description | Example |
| :--- | :--- | :--- |
| `BOT_TOKEN` | Telegram Bot Token from [@BotFather](https://t.me/BotFather) | `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ` |
| `MAIN_CHANNEL_ID` | Public Telegram Broadcast Channel ID / Username | `-1001234567890` or `@mpsc_study_hub` |
| `STAGING_CHANNEL_ID` | Private Admin Staging Channel ID for Moderation | `-1009876543210` |
| `BACKUP_CHANNEL_ID` | Private Telegram Channel for Daily DB Backups | `-1001122334455` |
| `ADMIN_USER_IDS` | Comma-separated Telegram User IDs of Admins | `123456789,987654321` |
| `DATABASE_URL` | Async database connection URL (PostgreSQL or SQLite) | `postgresql+asyncpg://studyuser:studypassword@localhost:5432/studybot_db` |
| `POSTGRES_USER` | PostgreSQL Username (for Docker Compose) | `studyuser` |
| `POSTGRES_PASSWORD` | PostgreSQL Password (for Docker Compose) | `studypassword` |
| `POSTGRES_DB` | PostgreSQL Database Name (for Docker Compose) | `studybot_db` |
| `SCRAPE_INTERVAL_MINUTES` | Frequency in minutes to scrape exam portals | `15` |
| `BACKUP_INTERVAL_HOURS` | Frequency in hours to upload database backups | `24` |

---

## 🛠️ Local Development & Testing

```bash
# 1. Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Run automated test suite
pytest -v tests/

# 3. Run application
python main.py
```

---

## 🚀 Production Deployment on Clean Oracle Cloud Ubuntu VM (Ampere A1 / x86_64)

### Method 1: Docker Compose (Recommended)

```bash
# 1. Update system & install Docker & Docker Compose
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-v2 git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

# 2. Clone repository & set up environment
git clone https://github.com/your-org/telegram_study_platform.git
cd telegram_study_platform
cp .env.example .env
nano .env  # Configure your BOT_TOKEN and Channel IDs

# 3. Start PostgreSQL 16 + Redis 7 + Bot Stack
docker compose up -d --build

# 4. View live logs
docker compose logs -f bot
```

---

### Method 2: Native systemd Service (with PostgreSQL or SQLite)

```bash
# 1. Install system dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git build-essential libpq-dev

# 2. Setup project & virtualenv
cd /home/ubuntu
git clone https://github.com/your-org/telegram_study_platform.git
cd telegram_study_platform
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3. Setup environment & directories
mkdir -p data downloads backups
cp .env.example .env
nano .env

# 4. Install and enable systemd service
sudo cp deploy/studybot.service /etc/systemd/system/studybot.service
sudo systemctl daemon-reload
sudo systemctl enable --now studybot

# 5. Monitor service
sudo systemctl status studybot
sudo journalctl -u studybot -f
```
