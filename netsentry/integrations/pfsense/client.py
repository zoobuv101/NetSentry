"""pfSense SSH client."""

from __future__ import annotations

import asyncio
import logging
import os

from netsentry.integrations.pfsense.exceptions import (
    PfSenseCommandError,
    PfSenseConnectionError,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 15.0
_DEFAULT_PORT = 22


class PfSenseClient:
    """
    Async SSH client for pfSense, wrapping paramiko via asyncio.run_in_executor.

    Paramiko is synchronous, so all blocking SSH calls run in a thread pool
    to keep the asyncio event loop free.
    """

    def __init__(
        self,
        host: str,
        username: str,
        key_path: str,
        port: int = _DEFAULT_PORT,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._host = host
        self._username = username
        self._key_path = key_path
        self._port = port
        self._timeout = timeout

    @classmethod
    def from_settings(cls) -> PfSenseClient:
        """
        Create a PfSenseClient from environment variables.

        Raises:
            ValueError: If required env vars are missing.
        """
        host = os.environ.get("PFSENSE_HOST")
        if not host:
            raise ValueError("PFSENSE_HOST environment variable not set")

        username = os.environ.get("PFSENSE_USERNAME", "admin")
        key_path = os.environ.get("PFSENSE_KEY_PATH", "/root/.ssh/id_rsa")
        port = int(os.environ.get("PFSENSE_SSH_PORT", "22"))

        return cls(host=host, username=username, key_path=key_path, port=port)

    async def run_command(self, command: str) -> tuple[str, str]:
        """
        Execute a command on pfSense via SSH.

        Returns:
            (stdout, stderr) tuple.

        Raises:
            PfSenseConnectionError: On SSH connection failure.
            PfSenseCommandError: On non-zero exit code.
        """
        try:
            return await self._execute(command)
        except PfSenseConnectionError:
            raise
        except Exception as e:
            raise PfSenseConnectionError(f"SSH command failed on {self._host}: {e}") from e

    async def _execute(self, command: str) -> tuple[str, str]:
        """
        Internal: run an SSH command in a thread executor.
        Raises PfSenseConnectionError on any SSH failure.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._run_sync, command)

    def _run_sync(self, command: str) -> tuple[str, str]:
        """Synchronous SSH execution (runs in thread pool)."""
        try:
            import paramiko
        except ImportError as e:
            raise PfSenseConnectionError("paramiko is not installed") from e

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(
                hostname=self._host,
                port=self._port,
                username=self._username,
                key_filename=self._key_path,
                timeout=self._timeout,
                look_for_keys=False,
                allow_agent=False,
            )
            _, stdout, stderr = ssh.exec_command(command, timeout=self._timeout)
            out = stdout.read().decode(errors="replace")
            err = stderr.read().decode(errors="replace")
            exit_code = stdout.channel.recv_exit_status()
            if exit_code != 0:
                raise PfSenseCommandError(f"Command exited {exit_code}: {err.strip()}")
            return out, err
        except (PfSenseCommandError, PfSenseConnectionError):
            raise
        except Exception as e:
            raise PfSenseConnectionError(f"SSH connection failed to {self._host}: {e}") from e
        finally:
            ssh.close()
