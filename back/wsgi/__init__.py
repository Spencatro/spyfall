import json
import random
from flask import Flask, jsonify, request, redirect, url_for
from flask import render_template, abort
import urllib
from flask.ext.pymongo import PyMongo

class SpyfallApp(Flask):

    def __init__(self, arg):
        super(SpyfallApp, self).__init__(arg)
        self.route("/")(self.index)
        self.route("/confirm_player/<game_name>/<player_name>/")(self.confirm_player)
        self.route("/debug/<command>/")(self.debug)
        self.route("/delete_all_games/super_secret_password/")(self.delete_all_games)
        self.route("/dump_db/")(self.dump_db)
        self.route("/game_exists/<game_name>/")(self.game_exists)
        self.route("/game_state/<game_name>/")(self.get_game_state)
        self.route("/join_game/<game_name>/<player_name>/")(self.join_game)
        self.route("/list_games/")(self.list_games)
        self.route("/list_location_objects/")(self.list_location_objects)
        self.route("/list_players_in_game/<game_name>/")(self.list_players_in_game)
        self.route("/map/super_secret_password/")(self.map)
        self.route("/new_game/<game_name>/<player_name>/")(self.new_game)
        self.route("/player_role/<game_name>/<player_name>/")(self.get_player_role)
        self.route("/remove_player_from_game/<game_name>/<player_name>/")(self.remove_player_from_game)
        self.route("/remote_log/<game_name>/<player_name>/<timestamp>/<log_str>")(self.remote_log)
        self.route("/reset_game/<game_name>/<end_type>/")(self.reset_game)
        self.route("/show_logs/")(self.show_logs)

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

    def list_location_objects(self):
        map_dict = {}
        for map_obj in self.mongo.db.maps.find():
            map_dict[map_obj['name']] = None
            if 'img_url' in map_obj.keys():
                map_dict[map_obj['name']] = map_obj['img_url']
        return self.allow_cross(jsonify(map_dict))

    def set_mongo(self, mongo):
        self.mongo = mongo

    def has_no_empty_params(self, rule):
        defaults = rule.defaults if rule.defaults is not None else ()
        arguments = rule.arguments if rule.arguments is not None else ()
        return len(defaults) >= len(arguments)

    def allow_cross(self, return_value, code=200):
        return return_value, code, {'Access-Control-Allow-Origin': '*'}

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

    def new_log_object(self, game_name, player_name, timestamp, log_str):
        d = {}
        d['game_name'] = game_name
        d['player_name'] = player_name
        d['log'] = log_str
        d['timestamp'] = timestamp
        return d

    def new_game(self, game_name, player_name):
        result = {'game_created': game_name, 'already_existed':False, 'already_in_game':False}
        if not self.game_exists(game_name, no_http=True):
            self.mongo.db.games.insert(self.new_game_object(game_name, player_name))
        else:
            result['already_existed'] = True
        join_result = self.join_game(game_name, player_name, no_http=True)
        if 'already_in_game' in join_result.keys():
            result['already_in_game'] = True
        return self.allow_cross(jsonify(result))

    def delete_all_games(self):
        self.mongo.db.games.drop()
        return "success"

    def player_is_in_game(self, game_name, player_name):
        return self.mongo.db.games.find({"players.name":player_name, "name":game_name}).count() > 0

    def game_exists(self, game_name, no_http = False):
        result = self.mongo.db.games.find({'name':game_name}).count() > 0
        if no_http:
            return result
        return self.allow_cross(jsonify({"result":result}))

    def join_game(self, game_name, player_name, no_http=False):
        result = {'success':True, 'already_in_game':False}
        if not self.player_is_in_game(game_name, player_name):
            self.mongo.db.games.update({'name':game_name},{"$push":{'players':{'name':player_name, 'confirmed':False, 'role':"Player"}}})
        else:
            result['already_in_game'] = True
        if no_http:
            return result
        return self.allow_cross(jsonify(result))

    def remove_player_from_game(self, game_name, player_name):
        result = {'success':True, 'not_in_game':False}
        if not self.player_is_in_game(game_name, player_name):
            result['not_in_game'] = True
        else:
            self.mongo.db.games.update({'name':game_name, 'players.name':player_name}, {"$pull":{"players":{"name":player_name}}})
        return self.allow_cross(jsonify(result))

    def remote_log(self, game_name, player_name, timestamp, log_str):
        result = "ok"
        self.mongo.db.logs.insert(self.new_log_object(game_name, player_name, timestamp, log_str));
        return self.allow_cross(result)

    def show_logs(self):
        logs = self.mongo.db.logs.find()
        return jsonify({"logs":self.query_to_list(logs)})

    def list_players_in_game(self, game_name, no_http = False):
        player_obj = {}
        player_object_list = self.mongo.db.games.find_one({"name":game_name})['players']
        for p_obj in player_object_list:
            player_obj[p_obj['name']] = p_obj['confirmed']
        if no_http:
            return [key for key in player_obj.keys()]
        return self.allow_cross(jsonify({'players':player_obj}))

    def list_games(self):
        game_obj_list = self.query_to_list(self.mongo.db.games.find())
        game_list = []
        for obj in game_obj_list:
            game_name = obj['name']
            game_list.append(game_name)
        return self.allow_cross(jsonify({'games':game_list}))

    def get_game_state(self, game_name, no_http = False):
        state = self.mongo.db.games.find_one({'name':game_name})['state']
        if no_http:
            return state
        return self.allow_cross(jsonify({'state':state}))

    def get_player_role(self, game_name, player_name):
        result = {}
        location = self.mongo.db.games.find_one({"name":game_name})['map']
        players = self.mongo.db.games.find_one({"players.name":player_name, "name":game_name})['players']
        result['role'] = "Unknown"
        for player_obj in players:
            if player_name == player_obj['name']:
                result['role'] = player_obj['role']
        result['location'] = "Unknown"
        if result['role'] != "Spy":
            result['location'] = location
        return self.allow_cross(jsonify(result))

    def confirm_player(self, game_name, player_name):
        player_list = self.list_players_in_game(game_name, no_http=True)
        player_index = player_list.index(player_name)
        self.mongo.db.games.update({"name":game_name}, {"$set":{"players."+str(player_index)+".confirmed":True}})
        players = self.mongo.db.games.find_one({"name":game_name})['players']
        all_confirmed = True
        for player_obj in players:
            if player_obj['confirmed'] == False:
                all_confirmed = False
        random_player_index = None
        len_players = None
        random_player_name = None
        if all_confirmed and self.get_game_state(game_name, no_http=True) != "playing": # Skip process if game already playing
            # Pick a random map
            maps = self.get_map_list()
            random_map_index = random.randint(0, len(maps)-1)
            game_map = maps[random_map_index]
            self.mongo.db.games.update({"name":game_name}, {"$set":{"map":game_map, "state":"playing"}})
            # Pick a random spy
            players = self.list_players_in_game(game_name,no_http=True)
            len_players = len(players)
            random_player_index = random.randint(0, len_players-1)
            random_player_name = players[random_player_index]
            self.mongo.db.games.update({"name":game_name},{"$set":{"players."+str(random_player_index)+".role":"Spy"}})
        return self.allow_cross(jsonify({'success':True, 'r_int':random_player_index, 'r_name':random_player_name, 'len_p':len_players}))

    def reset_game(self, game_name, end_type):
        # Pick a random map
        maps = self.get_map_list()
        random_map_index = random.randint(0, len(maps)-1)
        game_map = maps[random_map_index]
        self.mongo.db.games.update({"name":game_name}, {"$set":{"map":game_map, "state":"playing"}})
        # Pick a random spy
        players = self.list_players_in_game(game_name,no_http=True)
        len_players = len(players)
        # Reset all players to "Player"
        for i in range(len_players):
            self.mongo.db.games.update({"name":game_name},{"$set":{"players."+str(i)+".role":"Player"}})
        random_player_index = random.randint(0, len_players-1)
        random_player_name = players[random_player_index]
        self.mongo.db.games.update({"name":game_name},{"$set":{"players."+str(random_player_index)+".role":"Spy"}})
        return self.allow_cross(jsonify({"success":True}))

app = SpyfallApp(__name__)
app.config['MONGO_PORT'] = 27021
app.config['MONGO_DBNAME'] = "spyfall"
mongo = PyMongo(app)
app.set_mongo(mongo)

if __name__ == "__main__":
    app.run(debug = "True")
