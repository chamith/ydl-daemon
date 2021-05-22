#! /usr/bin/python3

from __future__ import unicode_literals
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import youtube_dl
import threading
import os
import datetime
import time
import sys
import getopt
from pathlib import Path
import re
import dal

DEFAULT_CONFIG='doda.conf'
DEFAULT_DB='doda.db'
DEFAULT_DOWNLOAD_DIR = os.getcwd()
DEFAULT_OFFPEAK_START = datetime.time(0, 0, 00)
DEFAULT_OFFPEAK_END = datetime.time(23, 59, 59)

def get_opt_val(opts, key, key_long, default_value):
    for opt in opts:
        if opt[0] in (key, key_long):
            return opt[1]
    return default_value

def get_config_settings():
    config_settings = {}

    if not os.path.isfile(CONFIG_FILE):
        return config_settings

    with open(CONFIG_FILE) as f_in:
        lines = filter(None, ((not line.startswith('#') and line.rstrip()) for line in f_in))

        for line in lines:
            line = line.split('=')
            config_settings[line[0]] = line[1]

    return config_settings

def get_offpeak_time(configs, default_start_time, default_finish_time):
    offpeak_from_config = configs.get('offpeak', None)
    
    if offpeak_from_config is None:
        return default_start_time, default_finish_time

    try:
        time_array = offpeak_from_config.split('-')
        return datetime.datetime.strptime(time_array[0],'%H:%M:%S').time(), datetime.datetime.strptime(time_array[1],'%H:%M:%S').time()
    except:
        return default_start_time, default_finish_time

opts, args = getopt.getopt(sys.argv[1:], "d:c:",['database=', 'config='])

DB_FILE = get_opt_val(opts, '-d','--database', DEFAULT_DB)
CONFIG_FILE = get_opt_val(opts, '-c','--config', DEFAULT_CONFIG)

print('Config File:{}'.format(CONFIG_FILE))
print('DB File:{}'.format(DB_FILE))

configs = get_config_settings()
dal.init(DB_FILE)

def run_web_server():

    app = Flask(__name__, static_url_path='/web-ui')
    CORS(app)

    @app.route('/')
    def root():
        return send_from_directory('web-ui', 'index.html')

    @app.route('/<path:path>')
    def send_js(path):
        return send_from_directory('web-ui', path)

    @app.route('/api/requests', methods=['GET'])
    def get_requests():
        return jsonify(dal.get_requests())

    @app.route('/api/requests/<int:id>', methods=['GET'])
    def get_request(id):
        return jsonify(dal.get_request(id))

    @app.route('/api/requests/<int:id>', methods=['DELETE'])
    def delete_request(id):
        dal.delete_request(id)
        return jsonify()

    @app.route('/api/requests', methods=['DELETE'])
    def clean_completed_requests():
        dal.delete_complete_requests()
        return jsonify()

    @app.route('/api/requests', methods=['POST'])
    def add_request():
        content = request.json
        schedule = int(content.get('schedule', 0))
        url = content.get('url', None)

        if url is None:
            return jsonify(''), 400

        req = dal.queue_request(url, schedule)
        resolver_thread = threading.Thread(target=dal.resolve_items, args=(req,))
        resolver_thread.start()
        return jsonify(req), 201

    @app.route('/api/items', methods=['GET'])
    def get_items():
        return jsonify(dal.get_items(3, 1))

    @app.route('/api/items/<string:id>', methods=['DELETE'])
    def delete_item(id):
        dal.delete_item(id)
        return jsonify()
        
    if __name__ == '__main__':
        app.run(host='0.0.0.0', debug=False)

def status_hook(d):

    if d['status'] == 'downloading':
        progress = d['downloaded_bytes']/d['total_bytes']*100
        dal.update_item_progress(d['filename'], 1, progress)
        print(round(progress, 1), '%')

    elif d['status'] == 'finished':
        dal.update_item_progress(d['filename'], 3, 100)

    elif d['status'] == 'error':
        dal.update_item_progress(d['filename'], -1)

    else:
        print('pending')

def isNowInTimePeriod(startTime, endTime, nowTime):
    if startTime < endTime:
        return startTime <= nowTime <= endTime
    else:  # Over midnight
        return nowTime >= startTime or nowTime <= endTime

def clean_string(str):
    return str.replace('/','_')

def run_downloader():

    print("Starting the download server ...")

    off_peak_start, off_peak_end = get_offpeak_time(configs, DEFAULT_OFFPEAK_START, DEFAULT_OFFPEAK_END)
    download_dir = configs.get('download_directory', DEFAULT_DOWNLOAD_DIR)

    print("===== CONFIGS =====")
    print('Download Directory: %s' % (download_dir))
    print('Off Peak Schedule: %s - %s' % (off_peak_start, off_peak_end))
    print('===================')

    while True:
        time_now = datetime.datetime.now().time()
        is_off_peak = isNowInTimePeriod(
            off_peak_start, off_peak_end, time_now)

        schedule_text = 'Off Peak' if is_off_peak else 'Peak'

        print('Current Schedule: {}'.format(schedule_text))

        items = dal.get_next_items(2, not is_off_peak, 1)

        opts = {
            'format': 'best',
            'progress_hooks': [status_hook]
        }

        for item in items:
            url = "https://www.youtube.com/watch?v=" + item['id']

            if item['r_type'] == 'video':
                opts['outtmpl'] = download_dir + '/%(title)s [%(uploader)s]-%(id)s.%(ext)s'
            else:
                dir_name = '{playlist} [{uploader}]'.format(uploader=clean_string(item['r_uploader']), playlist=clean_string(item['r_title']))
                opts['outtmpl'] = download_dir + '/' + dir_name + '/%(title)s - %(id)s.%(ext)s'

            with youtube_dl.YoutubeDL(opts) as ydl:
                ydl.download([url])

        time.sleep(10)

try:
    downloader_thread = threading.Thread(target=run_downloader)
    downloader_thread.start()
except:
    print('error starting the download server')

# with daemon.DaemonContext:
run_web_server()
