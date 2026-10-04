"""Local atomic replacement and process-safe locks shared by all writers."""
import os
import tempfile
import stat
from contextlib import contextmanager


def acquire_lock(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    handle = open(path, 'a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b'\0')
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise IOError('Another operation is using this file')
    return handle


def release_lock(handle):
    if handle is not None:
        # Closing releases the OS lock, including when the process exits.
        handle.close()


@contextmanager
def file_lock(path):
    handle = acquire_lock(path)
    try:
        yield
    finally:
        release_lock(handle)


def atomic_write(path, data):
    """Replace a local file; a failed replacement leaves the original intact.

    Callers performing read/modify/write must hold file_lock(path + '.lock')
    for the whole transaction. Temporary files are unique and on the same volume.
    """
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + os.path.basename(path) + '.', dir=parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            if stream.write(data) != len(data):
                raise IOError('Incomplete file write')
            stream.flush()
            os.fsync(stream.fileno())
        if os.path.exists(path):
            os.chmod(tmp, stat.S_IMODE(os.stat(path).st_mode))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
