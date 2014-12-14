#!/usr/bin/python
import sys
import logging
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, r'/var/www/spyfall/back/')
from wsgi import app as application
application.secret_key = 'SUPER SECRET WAHAHA'
