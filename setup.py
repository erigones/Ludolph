#!/usr/bin/env python

from distutils.core import setup
from ludolph.core import RPI

setup(name = 'ludolph',
    version = RPI.__version__,
    description = 'Zabbix monitoring Jabber bot',
    author = 'Richard Kellner, Daniel Kontsek',
    author_email = 'richard.kellner@ajty.info, daniel.kontsek@gmail.com',
    url = 'https://github.com/ricco386/Ludolph/downloads',
    license = 'GPLv3',
    packages = ['ludolph'],
    scripts = ['bin/ludolph'],
    data_files = [('/etc/init.d', ['init.d/ludolph'])],
    requires = ['jabberbot (>=0.15)', 'xmpppy'],
    classifiers = [
        'Environment :: Console',
        'Intended Audience :: System Administrators',
        'Operating System :: Unix',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python',
        'Topic :: Communications :: Chat',
        'Topic :: Utilities'],
    )
