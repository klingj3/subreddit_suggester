#!/usr/bin/python3
import os
import sys
import logging

def execfile(filename):
    globals = dict( __file__ = filename )
    exec( open(filename).read(), globals )

activate_this = os.path.join('/var/www/subreddit_suggestor/src/venv/bin', 'activate_this.py' )
execfile( activate_this )

logging.basicConfig(stream=sys.stderr)
sys.path.insert(0,"/var/www/subreddit_suggestor/src")
os.chdir('/var/www/subreddit_suggestor/src')
from server import app as application
application.secret_key = os.getenv('SECRET_KEY', 'for dev')