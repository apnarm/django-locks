#!/usr/bin/env python

from setuptools import setup

setup(
    name='django-locks',
    version='0.0.1',
    description='Database and filesystem locks for Django',
    author='Raymond Butcher',
    author_email='randomy@gmail.com',
    url='https://github.com/apn-online/django-locks',
    license='MIT',
    packages=(
        'django_locks',
    ),
    scripts=(
        'bin/lock-abort',
        'bin/lock-block',
    ),
    install_requires=(
        'django',
    ),
)
