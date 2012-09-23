#!/usr/bin/env python

from distutils.core import setup

setup(name='ludolph',
    version='0.1.0',
    description='Jabber bot',
    author='Richard Kellner',
    author_email='richard.kellner@ajty.info',
    url='https://github.com/ricco386/Ludolph/',
    license='GPLv3',
    packages=['ludolph'],
    scripts=['bin/ludolph'],
    data_files=[('/etc/init.d', ['init.d/ludolph'])],
    requires=['jabberbot (>=0.15)', 'xmpppy'],
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: System Administrators',
        'Operating System :: Unix',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python',
        'Topic :: Communications :: Chat',
        'Topic :: Utilities'],
    )
