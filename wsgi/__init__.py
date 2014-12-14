import os
# import pygst
import json
import threading
import pprint
from flask import Flask, jsonify, request, redirect, url_for
from flask import render_template, abort
from flask import request
import requests
import time
import threading

DB_JSON_FILE = r'/var/www/spyfall/db.json'

class SpyfallApp(Flask):

    def __init__(self, arg):
        super(SpyfallApp, self).__init__(arg)
        self.route("/")(self.index)
        self.route("/debug/<command>")(self.debug)
        self.route("/new_game/<game_name>")(self.debug)

    def load_db_file(self):
        with open(DB_JSON_FILE) as fp:
            jsonificated = json.load(fp)
        return jsonificated

    def overwrite_db(self, new_contents):
        with open(DB_JSON_FILE, 'w') as wfp:
            json.dump(new_contents, wfp)
        return "success"

    def index(self):
        return "<h1>Spyfall backend</h1>"

    def debug(self, command):
        return str(eval(command))

    def dump_db(self):
        return jsonify(self.load_db_file())

    def new_game(self, game_name):
        db = self.load_db_file()
        db['games'][game_name] = {}
        self.overwrite_db(db)
        return "Success: ",game_name

    def list_games(self):
        db_file = self.load_db_file()


app = SpyfallApp(__name__)

if __name__ == "__main__":
    app.run(debug = "True")
