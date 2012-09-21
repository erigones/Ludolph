#!/usr/bin/env python

from distutils.core import setup

setup(name='ludolph',
    version='0.1',
    description='Jabber bot',
    author='Richard Kellner',
    author_email='richard.kellner@ajty.info',
    url='https://github.com/ricco386/Ludolph/',
    license='GPLv3',
    packages=['ludolph'],
    scripts=['bin/ludolph'],
    requires=['JabberBot (>=0.15)']
    )
