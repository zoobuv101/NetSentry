"""
US0009 — TDD tests for the TP-Link Deco local API client.
Covers: AES/RSA encrypted JSON protocol, session management,
auto re-auth on 403, credential loading, timeout handling.
All HTTP calls mocked — no real Deco required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# ── Crypto module ─────────────────────────────────────────────────────────────


class TestDecoCrypto:
    def test_aes_encrypt_decrypt_roundtrip(self) -> None:
        """AES-CBC encrypt then decrypt returns original plaintext."""
        from netsentry.integrations.deco.crypto import aes_decrypt, aes_encrypt

        key = b"0123456789abcdef"  # 16-byte key
        iv = b"fedcba9876543210"  # 16-byte IV
        plaintext = b'{"operation": "read"}'

        ciphertext = aes_encrypt(plaintext, key, iv)
        assert ciphertext != plaintext

        recovered = aes_decrypt(ciphertext, key, iv)
        assert recovered == plaintext

    def test_aes_encrypt_produces_bytes(self) -> None:
        """aes_encrypt returns bytes."""
        from netsentry.integrations.deco.crypto import aes_encrypt

        key = b"0123456789abcdef"
        iv = b"fedcba9876543210"
        result = aes_encrypt(b"hello", key, iv)
        assert isinstance(result, bytes)

    def test_rsa_encrypt_produces_bytes(self) -> None:
        """rsa_encrypt returns base64 bytes using the provided public key."""
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.asymmetric import rsa

        from netsentry.integrations.deco.crypto import generate_aes_key, rsa_encrypt

        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=1024, backend=default_backend()
        )
        public_key = private_key.public_key()
        aes_key = generate_aes_key()
        encrypted = rsa_encrypt(aes_key, public_key)
        assert isinstance(encrypted, bytes)
        assert len(encrypted) > 0

    def test_generate_aes_key_is_16_bytes(self) -> None:
        """generate_aes_key produces a 16-byte random key."""
        from netsentry.integrations.deco.crypto import generate_aes_key

        key = generate_aes_key()
        assert isinstance(key, bytes)
        assert len(key) == 16


# ── DecoClient ────────────────────────────────────────────────────────────────


class TestDecoClient:
    def _make_client(self) -> object:
        from netsentry.integrations.deco.client import DecoClient

        return DecoClient(
            host="192.168.68.1",
            username="admin",
            password="password123",
        )

    @pytest.mark.asyncio
    async def test_authenticate_success(self) -> None:
        """Client authenticates and stores session state."""
        from netsentry.integrations.deco.client import DecoClient

        client = DecoClient(host="192.168.68.1", username="admin", password="secret")

        with patch.object(client, "_do_authenticate", new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = True
            result = await client.authenticate()

        assert result is True
        mock_auth.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_calls_authenticate_when_not_authenticated(self) -> None:
        """First request triggers authentication."""
        from netsentry.integrations.deco.client import DecoClient

        client = DecoClient(host="192.168.68.1", username="admin", password="secret")

        with (
            patch.object(client, "authenticate", new_callable=AsyncMock) as mock_auth,
            patch.object(client, "_do_request", new_callable=AsyncMock) as mock_req,
        ):
            mock_auth.return_value = True
            mock_req.return_value = {"result": "success", "data": {}}
            await client.request("POST", "/cgi-bin/luci/;stok=/ds", {"operation": "read"})

        mock_auth.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_reuses_session_when_authenticated(self) -> None:
        """Subsequent requests skip re-authentication."""
        from netsentry.integrations.deco.client import DecoClient

        client = DecoClient(host="192.168.68.1", username="admin", password="secret")
        client._authenticated = True  # Pre-set authenticated state

        with (
            patch.object(client, "authenticate", new_callable=AsyncMock) as mock_auth,
            patch.object(client, "_do_request", new_callable=AsyncMock) as mock_req,
        ):
            mock_req.return_value = {"result": "success", "data": {}}
            await client.request("POST", "/cgi-bin/luci/;stok=/ds", {})
            await client.request("POST", "/cgi-bin/luci/;stok=/ds", {})

        mock_auth.assert_not_called()
        assert mock_req.call_count == 2

    @pytest.mark.asyncio
    async def test_auto_reauth_on_403(self) -> None:
        """403 response triggers re-authentication and one retry."""
        from netsentry.integrations.deco.client import DecoClient

        client = DecoClient(host="192.168.68.1", username="admin", password="secret")
        client._authenticated = True

        call_count = 0

        async def mock_request_side_effect(*args, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                from netsentry.integrations.deco.exceptions import DecoAuthError

                raise DecoAuthError("403 Forbidden")
            return {"result": "success", "data": {}}

        with (
            patch.object(client, "_do_request", side_effect=mock_request_side_effect),
            patch.object(client, "authenticate", new_callable=AsyncMock) as mock_auth,
        ):
            mock_auth.return_value = True
            result = await client.request("POST", "/endpoint", {})

        mock_auth.assert_called_once()
        assert result == {"result": "success", "data": {}}

    @pytest.mark.asyncio
    async def test_raises_after_one_reauth_retry(self) -> None:
        """If re-auth also fails, DecoAuthError is raised."""
        from netsentry.integrations.deco.client import DecoClient
        from netsentry.integrations.deco.exceptions import DecoAuthError

        client = DecoClient(host="192.168.68.1", username="admin", password="secret")
        client._authenticated = True

        async def always_403(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise DecoAuthError("403")

        with (
            patch.object(client, "_do_request", side_effect=always_403),
            patch.object(client, "authenticate", new_callable=AsyncMock) as mock_auth,
        ):
            mock_auth.return_value = True
            with pytest.raises(DecoAuthError):
                await client.request("POST", "/endpoint", {})

        # authenticate called once (re-auth attempt), then fails again → raises
        mock_auth.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_timeout_raises(self) -> None:
        """Network timeout raises DecoConnectionError."""
        from netsentry.integrations.deco.client import DecoClient
        from netsentry.integrations.deco.exceptions import DecoConnectionError

        client = DecoClient(host="192.168.68.1", username="admin", password="secret")

        async def timeout_auth(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise DecoConnectionError("Connection timed out")

        with patch.object(client, "_do_authenticate", side_effect=timeout_auth):
            with pytest.raises(DecoConnectionError):
                await client.authenticate()

    def test_credentials_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DecoClient reads credentials from environment when not provided."""
        monkeypatch.setenv("DECO_HOST", "192.168.68.1")
        monkeypatch.setenv("DECO_USERNAME", "owner")
        monkeypatch.setenv("DECO_PASSWORD", "mypassword")

        from netsentry.integrations.deco.client import DecoClient

        client = DecoClient.from_settings()
        assert client._host == "192.168.68.1"
        assert client._username == "owner"

    def test_missing_host_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DecoClient.from_settings() raises if DECO_HOST not set."""
        monkeypatch.delenv("DECO_HOST", raising=False)
        monkeypatch.delenv("DECO_USERNAME", raising=False)
        monkeypatch.delenv("DECO_PASSWORD", raising=False)

        from netsentry.integrations.deco.client import DecoClient

        with pytest.raises(ValueError, match="DECO_HOST"):
            DecoClient.from_settings()
