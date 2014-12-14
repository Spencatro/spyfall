import json
import random
from flask import Flask, jsonify, request, redirect, url_for
from flask import render_template, abort
import urllib
from flask.ext.pymongo import PyMongo

DB_JSON_FILE = r'/var/www/spyfall/back/db.json'

class SpyfallApp(Flask):

    def __init__(self, arg):
        super(SpyfallApp, self).__init__(arg)
        self.route("/")(self.index)
        self.route("/map/super_secret_password/")(self.map)
        self.route("/debug/<command>/")(self.debug)
        self.route("/dump_db/")(self.dump_db)
        self.route("/new_game/<game_name>/<player_name>/")(self.new_game)
        self.route("/game_exists/<game_name>/")(self.game_exists)
        self.route("/list_games/")(self.list_games)
        self.route("/delete_all_games/super_secret_password/")(self.delete_all_games)
        self.route("/join_game/<game_name>/<player_name>/")(self.join_game)
        self.route("/confirm_player/<game_name>/<player_name>/")(self.confirm_player)
        self.route("/list_players_in_game/<game_name>/")(self.list_players_in_game)
        self.route("/remove_player_from_game/<game_name>/<player_name>/")(self.remove_player_from_game)
        self.route("/game_state/<game_name>/")(self.get_game_state)
        self.route("/player_role/<game_name>/<player_name>/")(self.get_player_role)
        self.route("/mongo_test/")(self.mongo_test)

        self.mongo = None

    def mongo_test(self):
        self.mongo.db.maps

    def set_mongo(self, mongo):
        self.mongo = mongo

    def has_no_empty_params(self, rule):
        defaults = rule.defaults if rule.defaults is not None else ()
        arguments = rule.arguments if rule.arguments is not None else ()
        return len(defaults) >= len(arguments)

    def allow_cross(self, return_value, code=200):
        return return_value, code, {'Access-Control-Allow-Origin': '*'}

    def load_db_file(self):
        with open(DB_JSON_FILE) as fp:
            jsonificated = json.load(fp)
        return jsonificated

    def overwrite_db(self, new_contents):
        with open(DB_JSON_FILE, 'w') as wfp:
            json.dump(new_contents, wfp)
        return "success"

    def map(self):
        output = []
        for rule in app.url_map.iter_rules():
            options = {}
            for arg in rule.arguments:
                options[arg] = "[{0}]".format(arg)

            methods = ','.join(rule.methods)
            url = url_for(rule.endpoint, **options)
            line = urllib.unquote("{:50s} {:20s} {}".format(rule.endpoint, methods, url))
            output.append(line)
        return jsonify({'map':output})


    def index(self):
        return self.allow_cross("<h1>Backend</h1>")


    def debug(self, command):
        return str(eval(command))

    def dump_db(self):
        return jsonify(self.load_db_file())

    def new_game(self, game_name, player_name):
        db = self.load_db_file()
        db['games'][game_name] = {}
        db['games'][game_name]['players'] = {}
        db['games'][game_name]['state'] = "adding"
        db['games'][game_name]['map'] = None
        self.overwrite_db(db)
        self.join_game(game_name, player_name)
        return self.allow_cross(jsonify({"game_created":game_name}))

    def delete_all_games(self):
        db = self.load_db_file()
        db['games'] = {}
        self.overwrite_db(db)
        return "success"

    def join_game(self, game_name, player_name):
        db_file = self.load_db_file()
        db_file['games'][game_name]['players'][player_name] = {'role':None, 'confirmed':False}
        self.overwrite_db(db_file)
        return self.allow_cross(jsonify({'success':True}))

    def remove_player_from_game(self, game_name, player_name):
        db = self.load_db_file()
        del db['games'][game_name]['players'][player_name]
        self.overwrite_db(db)
        return self.allow_cross(jsonify({'success':True}))

    def list_players_in_game(self, game_name):
        db = self.load_db_file()
        return self.allow_cross(jsonify({'players':db['games'][game_name]['players'].keys()}))

    def list_games(self):
        db_file = self.load_db_file()
        return self.allow_cross(jsonify({'games':db_file['games'].keys()}))

    def game_exists(self, game_name):
        db_file = self.load_db_file()
        games_list = db_file['games'].keys()
        if game_name in games_list:
            success = True
        else:
            success = False
        return self.allow_cross(jsonify({'result':success}))

    def get_game_state(self, game_name):
        db = self.load_db_file()
        state = db['games'][game_name]['state']
        return self.allow_cross(jsonify({'state':state}))

    def get_player_role(self, game_name, player_name):
        db = self.load_db_file()
        result = {}
        result['role'] = db['games'][game_name]['players'][player_name]['role']
        result['location'] = "Unknown"
        if result['role'] != "Spy":
            result['location'] = db['games'][game_name]['map']
        return self.allow_cross(jsonify(result))

    def confirm_player(self, game_name, player_name):
        db = self.load_db_file()
        db['games'][game_name]['players'][player_name]['confirmed'] = True
        players = db['games'][game_name]['players']
        all_confirmed = True
        for player_key in players.keys():
            if players[player_key]['confirmed'] == False:
                all_confirmed = False
        random_player_index = None
        len_players = None
        random_player_name = None
        if all_confirmed and db['games'][game_name]['state'] != "playing": # Skip process if game already playing
            # TODO: Always re-rolling, fix this
            # Pick a random map
            maps = db['maps']
            random_map_index = random.randint(0, len(maps)-1)
            map = maps[random_map_index]
            db['games'][game_name]['map'] = map
            db['games'][game_name]['state'] = "playing"
            # Pick a random spy
            players = db['games'][game_name]['players'].keys()
            len_players = len(players)
            random_player_index = random.randint(0, len_players-1)
            random_player_name = players = db['games'][game_name]['players'].keys()[random_player_index]
            for player_key in db['games'][game_name]['players'].keys():
                if player_key == random_player_name:
                    db['games'][game_name]['players'][player_key]['role'] = "Spy"
                else:
                    db['games'][game_name]['players'][player_key]['role'] = "Player"
        self.overwrite_db(db)
        return self.allow_cross(jsonify({'success':True, 'r_int':random_player_index, 'r_name':random_player_name, 'len_p':len_players}))

app = SpyfallApp(__name__)
app.config['MONGO_PORT'] = 27021
app.config['MONGO_DBNAME'] = "spyfall"
mongo = PyMongo(app)
app.set_mongo(mongo)

if __name__ == "__main__":
    app.run(debug = "True")
