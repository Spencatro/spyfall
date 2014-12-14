import os
# import pygst
import json
import threading
import pprint
from flask import Flask, jsonify, request, redirect, url_for
from flask import render_template, abort
from flask import request
from werkzeug import secure_filename
import requests
import time
import threading

import config
import vlc

if not os.path.exists(config.DB_JSON_FILE):
    # make the empty db file
    # Should only ever happen once
    with open(config.DB_JSON_FILE, 'w') as fp:
        empty_db = {"SCHEMA_VERSION":1.0}
        json.dump(empty_db, fp)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in config.ALLOWED_EXTENSIONS

class NetplixApp(Flask):

    def __init__(self, arg):
        super(NetplixApp, self).__init__(arg)
        self.vlc_instance = vlc.Instance()
        self.route("/")(self.index)
        self.route("/index/")(self.index)
        self.route("/dbdump/")(self.dbdump)
        self.route("/envinfo/")(self.envinfo)
        self.route("/search/by_title/<title>/")(self.search_by_title)
        self.route("/search/by_actor/<actor>/")(self.search_by_actor)
        self.route("/search/<search_string>/")(self.search)
        self.route("/play/<resource_id>/")(self.play)
        self.route("/stop_all/")(self.stop_all)
        self.route("/catalog/")(self.catalog)
        self.route("/seek/<resource_id>/<percent>/")(self.seek)
        self.route("/status/<resource_id>/")(self.status)
        self.route("/pause_renderer/")(self.pause_renderer)
        self.route("/play_renderer/")(self.play_renderer)
        # "Private" unlisted API
        self.route("/heartbeat/")(self.heartbeat)
        self.route("/cron_trigger/")(self.cron_proc)
        self.route('/upbloat/', methods=['GET', 'POST'])(self.upload)
        self.route("/secret_debug/<command>/")(self.debug)

    def load_db_file(self):
        with open(config.DB_JSON_FILE) as fp:
            jsonificated = json.load(fp)
        return jsonificated

    def get_playing_list(self):
        playing_list = []
        db_dict = self.load_db_file()
        max_id = int(db_dict['id_pointer'])
        for potential_id in range(max_id):
            res = self.vlc_instance.vlm_show_media(str(potential_id))
            if hasattr(res, 'title'):
                playing_list.append(potential_id)
        return playing_list


    def index(self):
        return "<h1>Netplix server</h1>" \
               "<p>The following is a short API for the Netplix server</p>" \
               "<p>All pages return a json file. Most languages can trivially parse json.</p>" \
               "<b>http://root-url/catalog</b>: shows a list of all resources in the database<br>" \
               "<b>http://root-url/pause_renderer/</b>: pauses the renderer playback<br>" \
               "<b>http://root-url/play_renderer/</b>: resumes playing after renderer is paused<br>" \
               "<b>http://root-url/play/[Integer ID]</b>: begins playing title by ID--not title!<br>" \
               "<p><b>http://root-url/search/[some string]</b>: searches both titles and actor lists<br>" \
               "<b>http://root-url/search/by_actor/[some string]</b>: searches by actor list only<br>" \
               "<b>http://root-url/search/by_title/[some string]</b>: searches by title only<br>" \
               "<b>http://root-url/stop_all/</b>: Stops all playing rtsp streams<br>" \
               "<b>http://root-url/[URL HIDDEN, ADMIN ONLY!]</b>: upload page</p>" \
               ""

    def debug(self, command):
        return str(eval(command))

    def catalog(self):
        return jsonify({'catalog':self.load_db_file()['catalog']})

    def seek(self, resource_id, percent):
        try:
            status = json.loads(self.vlc_instance.vlm_show_media("4"))['instances']['instance']
        except:
            time.sleep(.1)
            try:
                status = json.loads(self.vlc_instance.vlm_show_media("4"))['instances']['instance']
            except:
                time.sleep(.1)
                try:
                    status = json.loads(self.vlc_instance.vlm_show_media("4"))['instances']['instance']
                except:
                    return jsonify({'status':'error'}), 500
        current_percent = float(status['position'])
        if current_percent > float(percent):
            # mad haxx
            self.stop_all()
            time.sleep(.5)
            self.play(resource_id)
            time.sleep(.5)
        try:
            self.vlc_instance.vlm_seek_media(resource_id,float(percent))
        except:
            try:
                self.vlc_instance.vlm_seek_media(resource_id,float(percent))
            except:
                try:
                    self.vlc_instance.vlm_seek_media(resource_id,float(percent))
                except:
                    return jsonify({'status':'error'}), 500
        return jsonify({'status':'success'})

    def status(self, resource_id):
        try:
            status = json.loads(self.vlc_instance.vlm_show_media(resource_id))['instances']['instance']
        except:
            return jsonify({'state':'not playing'})
        return_dict = {}
        return_dict['position'] = status['position']
        return_dict['state'] = status['state']
        return jsonify(return_dict)

    def upload(self):
        if request.method == 'POST':
            file = request.files['file']
            actors = request.form['actors'].split(",")
            title = request.form['title']
            if not actors or not title:
                return "Error: Must complete form!"
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                db_dict = self.load_db_file()
                if not 'id_pointer' in db_dict:
                    db_dict['id_pointer'] = 10 # Just in case
                id_pointer = int(db_dict['id_pointer'])
                db_dict['catalog'].append({
                    'id':id_pointer,
                    'title':title,
                    'actors':actors,
                    'filepath':os.path.join(config.DATA_DIR,filename)
                })
                db_dict["id_pointer"] = id_pointer+1
                with open(config.DB_JSON_FILE,'w') as fp:
                    json.dump(db_dict, fp)
                return "Success! File "+str(filename)+" was uploaded"+str(actors)
            else:
                return "Error: File "+str(file.filename)+" is not in allowed filetype list."
        return '''
        <!doctype html>
        <title>Upload new File</title>
        <h1>Upload new File</h1>
        <form action="" method=post enctype=multipart/form-data>
          <p><input type=file name=file><br>
             Title:<input type=text name=title><br>
             Actors (comma separated):<input type=text name=actors><br>
             <input type=submit value=Upload>
        </form>
        '''

    def clear_db(self):
        with open(config.DB_JSON_FILE, 'w') as fp:
            json.dump({'id_pointer':0,'catalog':[]}, fp)
        return "Success, db is empty"

    def envinfo(self):
        return jsonify(os.environ)

    def dbdump(self):
        return jsonify(self.load_db_file())

    def search_by_title(self, title):
        db_dict = self.load_db_file()
        results_arr = []
        catalog = db_dict['catalog']
        for catalog_object in catalog:
            if title.lower() in catalog_object['title'].lower():
                if catalog_object not in results_arr:
                    results_arr.append(catalog_object)
        return jsonify({'results':results_arr})


    def search_by_actor(self, actor):
        db_dict = self.load_db_file()
        results_arr = []
        catalog = db_dict['catalog']
        for catalog_object in catalog:
            for actor_string in catalog_object['actors']:
                if actor.lower() in actor_string.lower():
                    if catalog_object not in results_arr:
                        results_arr.append(catalog_object)
        return jsonify({'results':results_arr})

    def search(self, search_string):
        db_dict = self.load_db_file()
        results_arr = []
        catalog = db_dict['catalog']
        for catalog_object in catalog:
            if search_string.lower() in catalog_object['title'].lower():
                if catalog_object not in results_arr:
                    results_arr.append(catalog_object)
                    continue
            for actor in catalog_object['actors']:
                if search_string.lower() in actor.lower():
                    if catalog_object not in results_arr:
                        results_arr.append(catalog_object)
                        continue
        return jsonify({'results':results_arr})

    def stop_all(self):
        result = ""
        for resource_id in self.get_playing_list():
            result += str(resource_id)+" "
            self.vlc_instance.vlm_stop_media(str(resource_id))
            self.vlc_instance.vlm_del_media(str(resource_id))
        return "Success: "+result

    def pause_renderer(self):
        db_dict = self.load_db_file()
        db_dict['current_command'] = "pause"
        with open(config.DB_JSON_FILE,'w') as fp:
            json.dump(db_dict, fp)
        return "Success"


    def play_renderer(self):
        db_dict = self.load_db_file()
        db_dict['current_command'] = "play"
        with open(config.DB_JSON_FILE,'w') as fp:
            json.dump(db_dict, fp)
        return "Success"

    def play(self, resource_id):
        result = self.stop_all()
        time.sleep(.1)
        db_dict = self.load_db_file()
        catalog = db_dict['catalog']
        resource = None
        for catalog_object in catalog:
            if str(catalog_object['id']) == str(resource_id):
                resource = catalog_object
                break

        if resource is None:
            # TODO: 404 here
            return "ERROR: Video with ID "+str(resource_id)+" does not exist!", 404
        title = resource['title']
        filepath = resource['filepath']

        rtsp_uri = 'rtsp://'+str(config.SERVER_IP)+':'+str(config.RENDERER_STREAM_PORT)+'/'+str(resource_id)+'.sdp'
        sout = '#rtp{dst='+config.SERVER_IP+',port='+str(config.SERVER_STREAM_PORT)+',sdp='+rtsp_uri+'}'

        def threading_target():
            self.vlc_instance.vlm_add_broadcast(str(resource_id), filepath, sout, 0, None, True, False)
            self.vlc_instance.vlm_play_media(str(resource_id))
            time.sleep(100)

        thread = threading.Thread(target=threading_target)
        thread.start()

        self.play_renderer()

        return jsonify({'title':title,'rtsp':rtsp_uri, "result":result})

    def heartbeat(self):
        db = self.load_db_file()
        uri = db['now_playing']
        command = db['current_command']
        return jsonify({'uri':uri, 'command':command})

    def cron_proc(self):
        db_dict = self.load_db_file()
        playing_list = self.get_playing_list()
        if len(playing_list) == 0:
            # db_dict['now_playing'] = None
            # with open(config.DB_JSON_FILE,'w') as fp:
            #     json.dump(db_dict, fp)
            return "Stream stopped"
        for resource_id in self.get_playing_list():
            db_dict['now_playing'] = 'rtsp://'+str(config.SERVER_IP)+':'+str(config.RENDERER_STREAM_PORT)+'/'+str(resource_id)+'.sdp'
            with open(config.DB_JSON_FILE,'w') as fp:
                json.dump(db_dict, fp)
            return "Stream running: "+str(resource_id)
        return "no update"

app = NetplixApp(__name__)
app.config['UPLOAD_FOLDER'] = config.DATA_DIR

if __name__ == "__main__":
    pass
    app.run(debug = "True")
