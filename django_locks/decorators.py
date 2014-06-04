"""
Locking decorators to ensure that a function cannot be run more than once at
any point in time.

Use 'lock' for general use. It will generate a lock based on the function.

@lock
def myfunc(x, y, z):
    return x + y + z


Use 'customlock' when you want to specify the name of the lock. You must
provide a lock name (string), or a function that accepts the decorated
function's arguments and returns a lock name (string).

@customlock('whatever')
def myfunc(x, y, z):
    return x + y + z

@customlock(lambda x, y, z: 'fancylock%d' % x)
def myfunc(x, y, z):
    return x + y + z

There are filesystem and database versions of each lock decorator.

"""

import contextlib
import os
import subprocess
import sys
import tempfile

from django.db import transaction
from django.utils.functional import wraps

from django_locks.models import Lock

try:
    import django_multidb
except ImportError:
    from django_locks.contexts.db import grab_db_lock
else:
    from django_locks.contexts.multidb import grab_db_lock


class LockDecorator(object):

    def __init__(self, name=None, wait=True):
        self.name = name
        self.wait = wait

    def __call__(self, func):

        @wraps(func)
        def wrapped_func(*args, **kwargs):

            if self.name:
                if callable(self.name):
                    lock_name = self.name(*args, **kwargs)
                else:
                    lock_name = self.name
            else:
                lock_name = '%s.%s' % (func.__module__, func.__name__)

            with self._grab_lock(lock_name) as success:
                if success:
                    return func(*args, **kwargs)

        return wrapped_func

    @contextlib.contextmanager
    def _grab_lock(self, lock_name):
        raise NotImplementedError('This must be implemented in a subclass.')


class DatabaseLockDecorator(LockDecorator):
    """
    A decorator class that creates a database lock, runs the decorated
    function, and then releases the lock when complete.

    """

    get_connection = get_database_connection()
    connections = TemporaryConnectionPool(alias_prefix='locking')

    @contextlib.contextmanager
    def _grab_lock(self, lock_name):
        with grab_db_lock(lock_name, self.wait) as success:
            yield success

    @contextlib.contextmanager
    def _grab_lock(self, lock_name):
        with self.get_connection() as using:
            with no_multidb():
                lock = Lock.grab(lock_name, wait=self.wait, using=using)
            success = bool(lock)
            yield success


class FileLockDecorator(LockDecorator):
    """
    A decorator class that creates a file lock using the "lockfile" program,
    runs the decorated function, and then deletes the lock when complete.

    Obviously, each server has its own file system, and is not aware
    of file locks that may exist on other servers.

    """

    def _run_lockfile(self, lock_path):

        if self.wait:
            command = (
                '/usr/bin/lockfile',
                '-1',  # sleeptime of 1 second
                '-r', '-1',  # retry forever
                '-l', '3600',  # ignore existing old lock files
                lock_path,
            )
        else:
            command = (
                '/usr/bin/lockfile',
                '-r', '0',  # do not retry; abort immediately
                '-l', '3600',  # ignore existing old lock files
                lock_path,
            )

        lockfile_stdout = tempfile.TemporaryFile()

        try:
            result = subprocess.call(command, stdout=lockfile_stdout, stderr=lockfile_stdout)
        except KeyboardInterrupt:
            return False

        if result == 73 and not self.wait:
            return False

        if result != 0:
            lockfile_stdout.seek(0)
            sys.stderr.write(lockfile_stdout.read())
            return False

        return True

    @contextlib.contextmanager
    def _grab_lock(self, lock_name):
        """
        Grab a file based lock using the "lockfile" program. Yields a "success"
        boolean indicating whether the lock was successfully acquired or not.

        """

        lock_path = '/tmp/lock-%s' % lock_name
        acquired = self._run_lockfile(lock_path)
        try:
            yield acquired
        finally:
            if acquired:
                os.remove(lock_path)


lock = DatabaseLockDecorator()
trylock = DatabaseLockDecorator(wait=False)
customlock = DatabaseLockDecorator

filelock = FileLockDecorator()
tryfilelock = FileLockDecorator(wait=False)
customfilelock = FileLockDecorator
