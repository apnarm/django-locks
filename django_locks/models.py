import datetime

from django.db import connections, models, transaction, DatabaseError

try:
    from psycopg2 import Error as PostgresError
    DatabaseErrors = (DatabaseError, PostgresError)
except ImportError:
    DatabaseErrors = (DatabaseErrors,)


DEFAULT_STALE_TIME = datetime.timedelta(hours=1)
MYSQL_LOCK_PREFIX = 'django-locks:'


class Lock(models.Model):

    name = models.CharField(max_length=200, unique=True)
    expires = models.DateTimeField(null=True)

    def __unicode__(self):
        return u'Lock: %s' % self.name

    @classmethod
    def _grab(cls, name, stale=DEFAULT_STALE_TIME, wait=True, using=None):

        cursor = connections[using].cursor()

        # Build the SQL that tries to grab the lock.
        sql = 'SELECT * FROM %s WHERE %s = %%s FOR UPDATE %s' % (
            Lock._meta.db_table,
            Lock._meta.get_field('name').column,
            not wait and 'NOWAIT' or '',
        )

        while True:

            savepoint = transaction.savepoint(using=using)
            try:
                cursor.execute(sql, [name])
                transaction.savepoint_commit(savepoint, using=using)

            except DatabaseErrors:
                transaction.savepoint_rollback(savepoint, using=using)
                if wait:
                    raise
                else:
                    return

            if cursor.rowcount:

                # Got the lock.
                lock = cls.objects.using(using).get(name=name)

                # Locks are supposed to clear the 'expires' value when they are
                # released. If it is not empty, then something probably went
                # wrong previously. This might happen if the locked function
                # commits the transaction. So don't use locks on functions with
                # custom transaction handling.
                if lock.expires:
                    # Only raise an exception if the lock has not expired yet.
                    assert lock.expires < datetime.datetime.now(), 'Grabbed a lock (%r) that is in use or broken!' % lock

                # Set the time for which this lock will expire.
                # It should clear the value when the lock is released, so this
                # value is only used if something has broken or the lock
                # decorator has been misused (e.g. using it on a function that
                # commits the transaction).
                lock.expires = datetime.datetime.now() + stale

                # Save the lock and return it.
                lock.save(using=using)
                return lock

            else:

                # Lock not found, so create it. Using get_or_create because
                # it can sometimes freak out when 2 things try to create
                # the lock at the same time.
                created_lock, created = cls.objects.using(using).get_or_create(name=name)
                if created:
                    transaction.commit(using=using)

    @classmethod
    def _grab_mysql(cls, name, stale=DEFAULT_STALE_TIME, wait=True, using=None):
        """
        MySQL does not support NOWAIT, but it does have some
        locking functions which can kind of make up for it.

        """

        connection = connections[using]
        cursor = connection.cursor()

        def get_lock(name, timeout):
            mysql_lock_name = MYSQL_LOCK_PREFIX + name
            cursor.execute('SELECT GET_LOCK(%s, %s)', [mysql_lock_name, timeout])
            return bool(cursor.fetchone()[0])

        acquired = False

        if wait:
            while not acquired:
                acquired = get_lock(name, 60)
        else:
            acquired = get_lock(name, 0)

        if acquired:
            # Always pass in wait=True to avoid using NOWAIT. In theory,
            # it should grab the lock immediately because the GET_LOCK()
            # lock has already been aquired.
            return cls._grab(name, stale=stale, wait=True, using=using)
        else:
            return None

    @classmethod
    def grab(cls, name, using, stale=DEFAULT_STALE_TIME, wait=True):
        connection = connections[using]
        using_mysql = 'mysql' in connection.settings_dict['ENGINE']
        if using_mysql:
            return cls._grab_mysql(name, stale=stale, wait=wait, using=using)
        else:
            return cls._grab(name, stale=stale, wait=wait, using=using)

    def release(self, using):
        self.delete(using=using)
        connection = connections[using]
        using_mysql = 'mysql' in connection.settings_dict['ENGINE']
        if using_mysql:
            cursor = connection.cursor()
            mysql_lock_name = MYSQL_LOCK_PREFIX + self.name
            cursor.execute('SELECT RELEASE_LOCK(%s)', [mysql_lock_name])
