"""Shared process locks and confirmation identity for local model operations."""

from contextlib import contextmanager
from dataclasses import asdict
from functools import wraps
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import errno
import json
import os
from pathlib import Path
import threading
import time

from src.config import embedding_models as definitions
from src.config.settings import load_embedding_model_settings


class ModelOperationBusyError(RuntimeError):
    """Another process currently owns the model inventory."""


_held = threading.local()


def model_preparation_binding(models_dir: Path | None = None) -> str:
    """Hash the configured path, pinned contract and installed library set."""

    root = (models_dir or load_embedding_model_settings().models_dir).expanduser().resolve()
    libraries = {}
    for name in ("transformers", "sentence-transformers", "fastembed", "huggingface-hub"):
        try:
            libraries[name] = version(name)
        except PackageNotFoundError:
            libraries[name] = None
    payload = {
        "models_dir": str(root),
        "dense": asdict(definitions.HARRIER_MODEL),
        "tokenizer": asdict(definitions.HARRIER_TOKENIZER),
        "sparse": asdict(definitions.BM25_MODEL),
        "pipeline": definitions.EMBEDDING_PIPELINE_VERSION,
        "manifest_format": definitions.MODEL_MANIFEST_FORMAT_VERSION,
        "libraries": libraries,
    }
    return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@contextmanager
def process_file_lock(stream, *, blocking: bool = True):
    """Lock one stable file until exit, including long Windows wait periods."""

    if os.name == "nt":
        import msvcrt

        if stream.seek(0, 2) == 0:
            stream.write(b"\0")
            stream.flush()
        while True:
            stream.seek(0)
            try:
                # LK_LOCK gives up after ten retries; explicitly retry the
                # nonblocking primitive so long builds serialize on Windows.
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError as error:
                if error.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                    raise
                if not blocking:
                    raise ModelOperationBusyError("Modellvorbereitung oder Indexjob ist bereits aktiv.") from None
                time.sleep(0.1)
    else:
        import fcntl

        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            raise ModelOperationBusyError("Modellvorbereitung oder Indexjob ist bereits aktiv.") from None
    try:
        yield
    finally:
        if os.name == "nt":
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def model_operation_lock(models_dir: Path | None = None, *, blocking: bool = True):
    """Hold an exclusive, thread-reentrant OS lock; never unlink its inode."""

    root = (models_dir or load_embedding_model_settings().models_dir).expanduser().resolve()
    held = getattr(_held, "roots", set())
    if root in held:
        yield root
        return
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".operation.lock"
    if path.is_symlink():
        raise OSError("Modellsperre darf kein Symlink sein.")
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "r+b") as stream, process_file_lock(stream, blocking=blocking):
        _held.roots = held | {root}
        try:
            yield root
        finally:
            _held.roots = held


def locked_model_operation(function):
    """Protect configured model consumers, including nested migration rechecks."""

    @wraps(function)
    def locked(*args, **kwargs):
        with model_operation_lock():
            return function(*args, **kwargs)
    return locked
