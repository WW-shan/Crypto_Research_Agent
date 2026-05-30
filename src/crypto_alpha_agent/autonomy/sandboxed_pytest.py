from __future__ import annotations

import argparse
import os
import site
import sys
import sysconfig
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m crypto_alpha_agent.autonomy.sandboxed_pytest"
    )
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--temp-root", required=True, type=Path)
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)

    pytest_args = list(args.pytest_args)
    if pytest_args[:1] == ["--"]:
        pytest_args = pytest_args[1:]

    workdir = args.workdir.resolve()
    temp_root = args.temp_root.resolve()
    _install_audit_hook(workdir=workdir, temp_root=temp_root)
    os.environ["HOME"] = str(temp_root)
    os.environ["TMPDIR"] = str(temp_root)
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    import pytest

    return int(pytest.main(pytest_args))


def _install_audit_hook(*, workdir: Path, temp_root: Path) -> None:
    allowed_read_prefixes = _allowed_read_prefixes(workdir=workdir, temp_root=temp_root)
    allowed_write_prefixes = (workdir, temp_root, *_device_paths())

    def hook(event: str, args: tuple[Any, ...]) -> None:
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            raise PermissionError("sandbox blocks network access")
        if event in {"subprocess.Popen", "os.system", "pty.spawn"}:
            raise PermissionError("sandbox blocks subprocess execution")
        if event == "open":
            _check_open(args, allowed_read_prefixes, allowed_write_prefixes)
            return
        if event in {
            "os.chdir",
            "os.listdir",
            "os.scandir",
            "os.remove",
            "os.rename",
            "os.replace",
            "os.rmdir",
            "os.unlink",
            "shutil.rmtree",
        }:
            _check_path_args(event, args, allowed_read_prefixes, allowed_write_prefixes)

    sys.addaudithook(hook)


def _allowed_read_prefixes(*, workdir: Path, temp_root: Path) -> tuple[Path, ...]:
    candidates = [
        workdir,
        temp_root,
        Path(sys.executable).resolve().parent,
        Path(sys.prefix).resolve(),
        Path(sys.base_prefix).resolve(),
        Path(sys.exec_prefix).resolve(),
    ]
    for key in ("stdlib", "platstdlib", "purelib", "platlib"):
        value = sysconfig.get_paths().get(key)
        if value:
            candidates.append(Path(value).resolve())
    for value in site.getsitepackages():
        candidates.append(Path(value).resolve())
    user_site = site.getusersitepackages()
    if user_site:
        candidates.append(Path(user_site).resolve())
    candidates.extend(_device_paths())
    return tuple(dict.fromkeys(path for path in candidates if path.exists()))


def _device_paths() -> tuple[Path, ...]:
    paths: list[Path] = []
    for value in ("/dev/null", "/dev/urandom", "/dev/random"):
        path = Path(value)
        if path.exists():
            paths.append(path.resolve())
    return tuple(paths)


def _check_open(
    args: tuple[Any, ...],
    allowed_read_prefixes: tuple[Path, ...],
    allowed_write_prefixes: tuple[Path, ...],
) -> None:
    if not args:
        return
    path = _coerce_path(args[0])
    if path is None:
        return
    mode = "" if len(args) <= 1 or args[1] is None else str(args[1])
    flags = args[2] if len(args) > 2 else 0
    resolved = path.resolve()
    if _is_write_mode(mode, flags):
        _require_prefix(resolved, allowed_write_prefixes, "write")
        return
    _require_prefix(resolved, allowed_read_prefixes, "read")


def _check_path_args(
    event: str,
    args: tuple[Any, ...],
    allowed_read_prefixes: tuple[Path, ...],
    allowed_write_prefixes: tuple[Path, ...],
) -> None:
    prefixes = allowed_write_prefixes if event in _WRITE_PATH_EVENTS else allowed_read_prefixes
    for raw in args[:2]:
        path = _coerce_path(raw)
        if path is not None:
            _require_prefix(path.resolve(), prefixes, event)


_WRITE_PATH_EVENTS = {
    "os.remove",
    "os.rename",
    "os.replace",
    "os.rmdir",
    "os.unlink",
    "shutil.rmtree",
}


def _coerce_path(raw: object) -> Path | None:
    if isinstance(raw, int):
        return None
    try:
        return Path(raw)  # type: ignore[arg-type]
    except TypeError:
        return None


def _is_write_mode(mode: str, flags: object) -> bool:
    if any(flag in mode for flag in ("w", "a", "x", "+")):
        return True
    if isinstance(flags, int):
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        return bool(flags & write_flags)
    return False


def _require_prefix(path: Path, prefixes: tuple[Path, ...], action: str) -> None:
    if any(_is_relative_to(path, prefix) for prefix in prefixes):
        return
    raise PermissionError(f"sandbox blocks {action} outside allowed paths: {path}")


def _is_relative_to(path: Path, prefix: Path) -> bool:
    try:
        path.relative_to(prefix)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
