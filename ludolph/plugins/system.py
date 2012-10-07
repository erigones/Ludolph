#!/usr/bin/python

import subprocess

def uptime():
    """
    Server uptime
    """
    return subprocess.check_output('uptime')

def who():
    """
    Users logged in on server
    """
    return subprocess.check_output('who')

def set_status(rpi, args):
    """
    Set status to jabberbot
    """
    rpi.status_message = args
    return
