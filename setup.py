#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2014 Erigones s. r. o.
# All Rights Reserved
#
# This software is licensed as described in the README.rst and LICENSE
# files, which you should have received as part of this distribution.

import sys
import codecs
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

# noinspection PyPep8Naming
from ludolph.__init__ import __version__ as VERSION

DESCRIPTION = 'Monitoring Jabber Bot'

with codecs.open('README.rst', 'r', encoding='UTF-8') as readme:
    LONG_DESCRIPTION = ''.join(readme)

if sys.version_info[0] < 3:
    DEPS = ['sleekxmpp>=1.1.11', 'bottle', 'dnspython']
else:
    DEPS = ['sleekxmpp>=1.1.11', 'bottle', 'dnspython3']

CLASSIFIERS = [
    'Environment :: Console',
    'Intended Audience :: System Administrators',
    'Operating System :: Unix',
    'Operating System :: POSIX :: Linux',
    'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 3',
    'Topic :: Communications :: Chat',
    'Topic :: Utilities'
]

packages = [
    'ludolph',
]

setup(
    name='ludolph',
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    author='Erigones',
    author_email='erigones [at] erigones.com',
    url='https://github.com/erigones/Ludolph/',
    license='GPLv3',
    packages=packages,
    scripts=['bin/ludolph'],
    install_requires=DEPS,
    platforms='Linux',
    classifiers=CLASSIFIERS,
    include_package_data=True
)
