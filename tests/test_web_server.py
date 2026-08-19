"""Unit Tests for Koyeb Web Health Server and Cloud DB URL Normalization."""

import pytest
from aiohttp.test_utils import TestClient, TestServer
from main import create_web_app
from database.session import normalize_db_url


@pytest.mark.asyncio
async def test_web_app_endpoints():
    """Verify / and /health routes respond with HTTP 200 and correct JSON structure."""
    app = create_web_app()
    server = TestServer(app)
    client = TestClient(server)

    await client.start_server()
    try:
        # Test GET /
        resp_root = await client.get("/")
        assert resp_root.status == 200
        data_root = await resp_root.json()
        assert data_root["status"] == "online"
        assert "bot" in data_root
        assert "version" in data_root

        # Test GET /health
        resp_health = await client.get("/health")
        assert resp_health.status == 200
        data_health = await resp_health.json()
        assert data_health["status"] == "healthy"
        assert data_health["bot_polling"] is True
        assert data_health["scraper_active"] is True
    finally:
        await client.close()


def test_cloud_db_url_normalization():
    """Verify normalization of various cloud PostgreSQL connection strings (Neon, Supabase, etc.)."""
    # 1. Neon/Render postgres:// format with sslmode
    neon_raw = "postgres://user:secret@ep-cool-fog.us-east-2.aws.neon.tech/neondb?sslmode=require"
    neon_norm = normalize_db_url(neon_raw)
    assert neon_norm.startswith("postgresql+asyncpg://")
    assert "ssl=require" in neon_norm

    # 2. Supabase postgresql:// format
    supabase_raw = "postgresql://postgres:password123@db.abcdefg.supabase.co:5432/postgres"
    supabase_norm = normalize_db_url(supabase_raw)
    assert supabase_norm.startswith("postgresql+asyncpg://")
    assert "db.abcdefg.supabase.co" in supabase_norm

    # 3. SQLite format remains untouched
    sqlite_raw = "sqlite+aiosqlite:///data/study_platform.db"
    assert normalize_db_url(sqlite_raw) == sqlite_raw
