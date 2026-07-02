"""Shared mock objects for deploy_unified tests."""

from __future__ import annotations


class _Channel:
    def __init__(self, status: int = 0) -> None:
        self._status = status

    def recv_exit_status(self) -> int:
        return self._status

    def shutdown_write(self) -> None:
        pass


class _Stdin:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.channel = _Channel()

    def write(self, data: str) -> None:
        self.writes.append(data)


class _Stream:
    def __init__(self, text: str = "", status: int = 0) -> None:
        self._text = text
        self.channel = _Channel(status)

    def read(self) -> bytes:
        return self._text.encode()


class _Sftp:
    def __init__(self) -> None:
        self.dirs = {"/"}
        self.mkdir_calls: list[str] = []
        self.put_calls: list[tuple[str, str]] = []
        self.closed = False

    def stat(self, path: str) -> object:
        if path not in self.dirs:
            raise FileNotFoundError(path)
        return object()

    def mkdir(self, path: str) -> None:
        self.mkdir_calls.append(path)
        self.dirs.add(path)

    def put(self, local: str, remote: str) -> None:
        self.put_calls.append((local, remote))

    def close(self) -> None:
        self.closed = True


class _DeploySsh:
    def __init__(self, sftp: _Sftp) -> None:
        self.sftp = sftp
        self.closed = False

    def load_system_host_keys(self) -> None:
        pass

    def connect(self, *args: object, **kwargs: object) -> None:
        pass

    def open_sftp(self) -> _Sftp:
        return self.sftp

    def exec_command(self, command: str) -> tuple[None, _Stream, _Stream]:
        raise AssertionError(f"deploy_files should not open exec channels: {command}")

    def close(self) -> None:
        self.closed = True


class _RestartSsh:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.closed = False

    def load_system_host_keys(self) -> None:
        pass

    def connect(self, *args: object, **kwargs: object) -> None:
        pass

    def exec_command(self, command: str) -> tuple[None, _Stream, _Stream]:
        self.commands.append(command)
        if command.startswith("curl "):
            if "/health/ready" in command:
                return None, _Stream('{"status":"ready","startup_status":"ready"}'), _Stream()
            return None, _Stream('{"status":"ok"}'), _Stream()
        return None, _Stream(), _Stream()

    def close(self) -> None:
        self.closed = True


class _PrepareSsh:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.closed = False

    def load_system_host_keys(self) -> None:
        pass

    def connect(self, *args: object, **kwargs: object) -> None:
        pass

    def exec_command(self, command: str) -> tuple[_Stdin, _Stream, _Stream]:
        self.commands.append(command)
        if "df -Pm" in command:
            return _Stdin(), _Stream("disk_free_mb=2048\nmem_available_mb=512\n"), _Stream()
        if "tar --ignore-failed-read" in command:
            return (
                _Stdin(),
                _Stream("/opt/lima-router/backups/unit-test-20260609_010203/runtime-before.tgz\n"),
                _Stream(),
            )
        return _Stdin(), _Stream(), _Stream()

    def close(self) -> None:
        self.closed = True
