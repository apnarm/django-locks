import contextlib

from django_locks.models import Lock


@contextlib.contextmanager
def grab_db_lock(lock_name, wait):
    """
    Grab a lock using the current database connection. Yields a "success"
    boolean indicating whether the lock was successfully acquired or not.

    WARNING: There may be issues if the code being wrapped by this context has
    custom transaction management. The multidb context solves this problem.

    """

    lock = Lock.grab(lock_name, wait=wait, using=using)
    success = bool(lock)
    try:
        yield success
    finally:
        if success:
            lock.release(using=using)
