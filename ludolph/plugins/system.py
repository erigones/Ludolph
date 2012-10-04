#!/usr/bin/python

import subprocess

def uptime():
    """
    Server uptime
    """
    return subprocess.check_output('uptime')

