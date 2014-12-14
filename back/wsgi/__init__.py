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

        self.mongo = None

    def query_to_list(self, query, remove_id = True):
        result = []
        for q in query:
            if remove_id:
                q.pop("_id")
            result.append(q)
        return result


    def get_map_list(self):
        mongo_result = self.mongo.db.maps.find()
        map_list = []
        for map in mongo_result:
            map_list.append(map['name'])
        return map_list

    def set_mongo(self, mongo):
        self.mongo = mongo

    def has_no_empty_params(self, rule):
        defaults = rule.defaults if rule.defaults is not None else ()
        arguments = rule.arguments if rule.arguments is not None else ()
        return len(defaults) >= len(arguments)

    def allow_cross(self, return_value, code=200):
        return return_value, code, {'Access-Control-Allow-Origin': '*'}

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
        games_query = self.mongo.db.games.find()
        maps_query = self.mongo.db.maps.find()

        return jsonify({'maps':self.get_map_list(), 'games':self.query_to_list(games_query)})

    def new_game_object(self, game_name, player_name):
        d = {}
        d['name'] = game_name
        d['players'] = []
        d['state'] = "adding"
        d['map'] = None
        return d

    def new_game(self, game_name, player_name):
        result = {'game_created': game_name, 'already_existed':False, 'already_in_game':False}
        if not self.game_exists(game_name):
            self.mongo.db.games.insert(self.new_game_object(game_name, player_name))
        else:
            result['already_existed'] = True
        join_result = self.join_game(game_name, player_name)
        if 'already_in_game' in join_result.keys():
            result['already_in_game'] = True
        return self.allow_cross(jsonify(result))

    def delete_all_games(self):
        db = self.load_db_file()
        db['games'] = {}
        self.overwrite_db(db)
        return "success"

    def player_is_in_game(self, game_name, player_name):
        return self.mongo.db.games.find({"players.name":player_name, "name":game_name}).count() > 0

    def game_exists(self, game_name):
        return self.allow_cross(jsonify({"result":self.mongo.db.games.find({'name':game_name}).count() > 0}))

    def join_game(self, game_name, player_name):
        result = {'success':True, 'already_in_game':False}
        if not self.player_is_in_game(game_name, player_name):
            self.mongo.db.games.update({'name':game_name},{"$push":{'players':{'name':player_name, 'confirmed':False, 'role':"unassigned"}}})
        else:
            result['already_in_game'] = True
        return self.allow_cross(jsonify(result))

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
            maps = self.get_map_list()
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
