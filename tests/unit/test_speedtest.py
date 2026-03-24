"""
US0034-US0037 — TDD tests for internet speed monitor.
Covers: LibreSpeed runner, Ookla fallback, result storage, API endpoint.
All subprocess calls mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# ── Speed test runner ─────────────────────────────────────────────────────────


class TestSpeedTestRunner:
    @pytest.mark.asyncio
    async def test_librespeed_returns_result(self) -> None:
        """LibreSpeed runner parses JSON output correctly."""
        from netsentry.speedtest.librespeed import run_librespeed

        fake_output = '{"download": 95.4, "upload": 45.2, "ping": 8.3, "server": {"name": "Local"}}'
        with patch(
            "netsentry.speedtest.librespeed._run_subprocess", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = (fake_output, "")
            result = await run_librespeed()

        assert result is not None
        assert abs(result.download_mbps - 95.4) < 0.1
        assert abs(result.upload_mbps - 45.2) < 0.1
        assert abs(result.ping_ms - 8.3) < 0.1
        assert result.server == "Local"
        assert result.backend == "librespeed"

    @pytest.mark.asyncio
    async def test_librespeed_tool_missing_returns_none(self) -> None:
        """Missing librespeed binary returns None gracefully."""
        from netsentry.speedtest.librespeed import run_librespeed

        with patch(
            "netsentry.speedtest.librespeed._run_subprocess", new_callable=AsyncMock
        ) as mock_run:
            mock_run.side_effect = FileNotFoundError("librespeed not found")
            result = await run_librespeed()

        assert result is None

    @pytest.mark.asyncio
    async def test_librespeed_invalid_json_returns_none(self) -> None:
        """Invalid JSON output returns None gracefully."""
        from netsentry.speedtest.librespeed import run_librespeed

        with patch(
            "netsentry.speedtest.librespeed._run_subprocess", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = ("not json", "")
            result = await run_librespeed()

        assert result is None

    @pytest.mark.asyncio
    async def test_ookla_returns_result(self) -> None:
        """Ookla runner parses official Ookla CLI JSON output (bandwidth in bytes/s)."""
        from netsentry.speedtest.ookla import run_ookla

        # Official Ookla CLI --format=json: bandwidth in bytes/s
        fake_output = """{
            "download": {"bandwidth": 112500000},
            "upload": {"bandwidth": 56250000},
            "ping": {"latency": 8.2},
            "server": {"name": "Airband Community", "location": "London"}
        }"""
        with patch("netsentry.speedtest.ookla._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (fake_output, "")
            result = await run_ookla()

        assert result is not None
        assert abs(result.download_mbps - 900.0) < 1.0  # 112500000 * 8 / 1e6
        assert abs(result.upload_mbps - 450.0) < 1.0
        assert abs(result.ping_ms - 8.2) < 0.1
        assert result.backend == "ookla"

    @pytest.mark.asyncio
    async def test_ookla_tool_missing_returns_none(self) -> None:
        """Missing speedtest-cli binary returns None gracefully."""
        from netsentry.speedtest.ookla import run_ookla

        with patch("netsentry.speedtest.ookla._run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = FileNotFoundError("speedtest not found")
            result = await run_ookla()

        assert result is None


# ── Speed test models ─────────────────────────────────────────────────────────


class TestSpeedTestModels:
    def test_speedtest_result_dataclass(self) -> None:
        """SpeedTestResult has all required fields."""
        from netsentry.speedtest.models import SpeedTestResult

        result = SpeedTestResult(
            download_mbps=100.0,
            upload_mbps=50.0,
            ping_ms=5.0,
            backend="librespeed",
        )
        assert result.download_mbps == 100.0
        assert result.server is None  # optional

    def test_speedtest_result_grade_excellent(self) -> None:
        """grade property returns 'excellent' for fast connections."""
        from netsentry.speedtest.models import SpeedTestResult

        result = SpeedTestResult(
            download_mbps=500.0, upload_mbps=200.0, ping_ms=5.0, backend="librespeed"
        )
        assert result.grade == "excellent"

    def test_speedtest_result_grade_poor(self) -> None:
        """grade property returns 'poor' for slow connections."""
        from netsentry.speedtest.models import SpeedTestResult

        result = SpeedTestResult(
            download_mbps=5.0, upload_mbps=2.0, ping_ms=150.0, backend="librespeed"
        )
        assert result.grade == "poor"


# ── Speed test storage ────────────────────────────────────────────────────────


class TestSpeedTestStorage:
    @pytest.fixture
    async def db_conn(self, tmp_path: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
        from netsentry.db.connection import get_connection, run_migrations

        db_path = str(tmp_path / "test.db")  # type: ignore[operator]
        run_migrations(db_path)
        conn = await get_connection(db_path)
        yield conn
        await conn.close()

    @pytest.mark.asyncio
    async def test_save_result_writes_to_db(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """save_result() writes speed test result to speed_tests table."""
        from netsentry.speedtest.models import SpeedTestResult
        from netsentry.speedtest.storage import SpeedTestStorage

        result = SpeedTestResult(
            download_mbps=95.0,
            upload_mbps=45.0,
            ping_ms=10.0,
            backend="librespeed",
            server="Test Server",
        )
        storage = SpeedTestStorage(conn=db_conn)
        await storage.save(result)

        async with db_conn.execute("SELECT * FROM speed_tests ORDER BY id DESC LIMIT 1") as cur:
            row = await cur.fetchone()

        assert row is not None
        assert abs(row["download_mbps"] - 95.0) < 0.1
        assert row["backend"] == "librespeed"
        assert row["server"] == "Test Server"

    @pytest.mark.asyncio
    async def test_get_latest_returns_most_recent(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """get_latest() returns the most recently stored speed test."""
        from netsentry.speedtest.models import SpeedTestResult
        from netsentry.speedtest.storage import SpeedTestStorage

        storage = SpeedTestStorage(conn=db_conn)
        await storage.save(
            SpeedTestResult(
                download_mbps=50.0, upload_mbps=20.0, ping_ms=15.0, backend="librespeed"
            )
        )
        await storage.save(
            SpeedTestResult(
                download_mbps=100.0, upload_mbps=50.0, ping_ms=8.0, backend="librespeed"
            )
        )

        latest = await storage.get_latest()
        assert latest is not None
        assert abs(latest.download_mbps - 100.0) < 0.1

    @pytest.mark.asyncio
    async def test_get_latest_returns_none_when_empty(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """get_latest() returns None when no tests have been run."""
        from netsentry.speedtest.storage import SpeedTestStorage

        storage = SpeedTestStorage(conn=db_conn)
        assert await storage.get_latest() is None

    @pytest.mark.asyncio
    async def test_get_history_returns_list(self, db_conn) -> None:  # type: ignore[no-untyped-def]
        """get_history() returns last N speed test results."""
        from netsentry.speedtest.models import SpeedTestResult
        from netsentry.speedtest.storage import SpeedTestStorage

        storage = SpeedTestStorage(conn=db_conn)
        for dl in [50.0, 75.0, 100.0]:
            await storage.save(
                SpeedTestResult(
                    download_mbps=dl, upload_mbps=dl / 2, ping_ms=10.0, backend="librespeed"
                )
            )

        history = await storage.get_history(limit=2)
        assert len(history) == 2
        # Most recent first
        assert history[0].download_mbps > history[1].download_mbps
