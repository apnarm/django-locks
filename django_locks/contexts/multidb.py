import contextlib

from django.db import transaction

from django_locks.models import Lock

from django_multidb.connection import connection_state
from django_multidb.pool import TemporaryConnectionPool


connections = TemporaryConnectionPool(alias_prefix='django-locks')


@contextlib.contextmanager
def grab_db_lock(lock_name, wait):
    """
    Grab a lock using a new, temporary connection. Yields a "success"
    boolean indicating whether the lock was successfully acquired or not.

    This context manager ensures that multidb does not override the
    connection when accessing the Lock model and its transaction. The
    code that runs within this context should NOT be affected - it must
    run as usual, with normal multidb functionality intact.

    """

    with connections.get() as using:

        try:

            with connection_state.force(None):
                transaction.enter_transaction_management(using=using)
                transaction.managed(True, using=using)
                lock = Lock.grab(lock_name, wait=wait, using=using)

            success = bool(lock)

            try:
                yield success
            finally:
                if success:
                    with connection_state.force(None):
                        lock.release(using=using)
                        transaction.commit(using=using)

        finally:
            with connection_state.force(None):
                transaction.leave_transaction_management(using=using)
