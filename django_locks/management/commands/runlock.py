import hashlib
import os
import subprocess

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from django_locks.decorators import customlock, customfilelock

try:
    import setproctitle
except ImportError:
    setproctitle = None


class Command(BaseCommand):

    help = 'Run a command with locking.'
    args = '<wait|nowait> <command>'
    wait_mode = None

    can_import_settings = False

    def handle(self, *args, **options):

        # Use environment variables and ignore any arguments passed in.
        # Allowing arguments makes it easier to debug when running "ps".
        wait_mode = os.environ.get('RUN_LOCK_WAIT_MODE')
        command = os.environ.get('RUN_LOCK_COMMAND')

        # Make this easier to find in process lists.
        if setproctitle:
            setproctitle.setproctitle('python runlock.py %s' % command)

        self.wait_mode = wait_mode

        if wait_mode == 'wait':
            wait = True
        elif wait_mode == 'nowait':
            wait = False
        else:
            raise CommandError(self.usage())

        if not command:
            raise CommandError(self.usage())

        # There's no need to keep the database connection open while this
        # runs. The db lock will create a different connection as needed.
        for connection in connections:
            connection.close()

        # Use a lock file (on disk) as a safety net, to prevent one machine
        # stacking up a bunch of blocking database locks. This is currently
        # not optional, simply because we have nothing requiring otherwise.
        lockfile_name = '%s-%s' % (
            os.path.basename(command),
            hashlib.md5(command).hexdigest(),
        )
        file_lock = customfilelock(lockfile_name, wait=False)

        # And use a database lock as the shared lock, to prevent
        # multiple machines from running the command at the same time.
        database_lock = customlock('runlock: %s' % command, wait=wait)

        @file_lock
        @database_lock
        def run():
            try:
                environment = dict(os.environ.items())
                environment['QUIET_MODE'] = environment.pop('OLD_QUIET_MODE', '')
                environment['DISABLE_DB_SETTINGS'] = environment.pop('OLD_DISABLE_DB_SETTINGS', '')
                subprocess.call(command, shell=True, env=environment)
            except KeyboardInterrupt:
                pass

        run()

    def usage(self, subcommand=None):
        if self.wait_mode == 'wait':
            return 'Usage: lock-block <command>'
        elif self.wait_mode == 'nowait':
            return 'Usage: lock-abort <command>'
        else:
            return 'Use the lock-abort or lock-block command.'
