#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2017 Erigones, s. r. o.
# All Rights Reserved
#
# This software is licensed as described in the README.rst and LICENSE
# files, which you should have received as part of this distribution.

import os
import sys

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

# noinspection PyPep8Naming
from ludolph import __version__ as VERSION


def read_file(name):
    return open(os.path.join(os.path.dirname(__file__), name)).read()


DEPS = [
    'ludolph-zabbix>=1.5',
    'sleekxmpp>=1.2.0,<1.4.0',
    'bottle',
]

if sys.version_info[0] < 3:
    DEPS.append('dnspython')

    if sys.version_info[0] == 2 and sys.version_info[1] < 7:
        DEPS.append('ordereddict')
else:
    DEPS.append('dnspython>=1.13.0')

CLASSIFIERS = [
    'Environment :: Console',
    'Intended Audience :: System Administrators',
    'Intended Audience :: Developers',
    'Operating System :: Unix',
    'Operating System :: POSIX :: Linux',
    'License :: OSI Approved :: BSD License',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 3',
    'Development Status :: 5 - Production/Stable',
    'Topic :: Communications :: Chat',
    'Topic :: Utilities'
]

setup(
    name='ludolph',
    version=VERSION,
    description='Monitoring Jabber Bot',
    long_description=read_file('README.rst'),
    author='Erigones',
    author_email='erigones@erigones.com',
    url='https://github.com/erigones/Ludolph/',
    license='BSD',
    packages=['ludolph'],
    scripts=['bin/ludolph'],
    install_requires=DEPS,
    platforms='any',
    classifiers=CLASSIFIERS,
    include_package_data=True
)
