#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2015 Erigones, s. r. o.
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
from ludolph.__init__ import __version__ as VERSION

read = lambda fname: open(os.path.join(os.path.dirname(__file__), fname)).read()

DEPS = ['zabbix-api-erigones', 'sleekxmpp>=1.1.11', 'bottle']

if sys.version_info[0] < 3:
    DEPS.append('dnspython')
else:
    DEPS.append('dnspython3')

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

packages = [
    'ludolph',
]

setup(
    name='ludolph',
    version=VERSION,
    description='Monitoring Jabber Bot',
    long_description=read('README.rst'),
    author='Erigones',
    author_email='erigones [at] erigones.com',
    url='https://github.com/erigones/Ludolph/',
    license='BSD',
    packages=packages,
    scripts=['bin/ludolph'],
    install_requires=DEPS,
    platforms='Linux',
    classifiers=CLASSIFIERS,
    include_package_data=True
)
