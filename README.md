django-locks 0.0.1
==================

**This library is not ready for use yet.**

Database and filesystem locks for Django.
Please read the section on *Database transactions*
before using this library.

It comes with decorators for locking functions
within your code, and also bin scripts for locking
shell commands (e.g. cron jobs).

Installation
------------

    pip install django-locks

Add `django_locks` to your INSTALLED_APPS list in Django.

Run Django's `syncdb` command to set up the database table.

Decorator Usage
---------------

To import database lock decorators:

    from django_locks.decorators import lock, trylock, customlock

Or for filesystem lock decorators:

    from django_locks.decorators import filelock, tryfilelock, customfilelock


Use `lock` or `filelock` for general use. It will
generate a blocking lock based on the function's
module and name.

Use `trylock` or `tryfilelock` if you want the function
call to be skipped rather than wait for the lock to
become available.

    @lock
    def myfunc(x, y, z):
        return x + y + z

Use `customlock` when you want to specify the name of
the lock. You must provide a lock name (string), or a
function that accepts the decorated function's arguments
and returns a lock name (string).

    @customlock('whatever')
    def myfunc(x, y, z):
        return x + y + z

    @customlock(lambda x, y, z: 'fancylock%d' % x)
    def myfunc(x, y, z):
        return x + y + z

Script Usage
------------

Two scripts, `lock-abort` and `lock-block` are
included in this library. These can be used to
add locking to any shell command.

They will execute the arguments as a command.

    $ lock-abort python my-script.py
    hello from my-script.py
    $ lock-block python my-script.py
    hello from my-script.py

The `lock-abort` script will not run the command
if a lock already exists for it. `lock-block` will
wait for the lock to become available.

Database transactions
---------------------

Database locks require a transaction, which can be
disrupted if a locked function uses custom transaction
management. Nested locks will also suffer from this
limitation.

To solve this, you can install the **django-readwrite**
library. This allows **django-locks** to interact with
the database using its own, separate connections.

The `lock-abort` and `lock-block` management commands
avoid the issues with transactions by running commands
in a subprocess. They do not require django-readwrite.
