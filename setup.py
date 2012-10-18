#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2012 Richard Kellner & Daniel Kontsek
# All Rights Reserved
#
# This software is licensed as described in the README.rst and LICENSE
# file, which you should have received as part of this distribution.

import codecs
try:
    from setuptools import setup, Command
except ImportError:
    from distutils.core import setup, Command

from ludolph.version import __version__

VERSION = __version__
DESCRIPTION = 'Monitoring Jabber bot'
with codecs.open('README.rst', 'r', encoding='UTF-8') as readme:
    LONG_DESCRIPTION = ''.join(readme)

CLASSIFIERS = [
    'Environment :: Console',
    'Intended Audience :: System Administrators',
    'Operating System :: Unix',
    'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
    'Programming Language :: Python',
    'Topic :: Communications :: Chat',
    'Topic :: Utilities'
]

packages = [
    'ludolph',
]

setup(
    name = 'ludolph',
    version = VERSION,
    description = DESCRIPTION,
    long_description = LONG_DESCRIPTION,
    author = 'Richard Kellner & Daniel Kontsek',
    author_email = 'richard.kellner [at] ajty.info, daniel.kontsek [at] gmail.com',
    url = 'https://github.com/ricco386/Ludolph/',
    license = 'GPLv3',
    packages = packages,
    scripts = ['bin/ludolph'],
    data_files = [('/etc/init.d', ['init.d/ludolph'])],
    install_requires = ['sleekxmpp'],
    classifiers = CLASSIFIERS
)
