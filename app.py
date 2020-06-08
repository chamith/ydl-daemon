#! /usr/bin/python3

from __future__ import unicode_literals
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import youtube_dl
import threading
import sqlite3
import os
import datetime
import time
import sys
import getopt
from pathlib import Path
import re

YOUTUBE_VIDEO_ID_LENGTH = 11
DEFAULT_CONFIG='youtube-dl-daemon.conf'
DEFAULT_DB='youtube-dl-daemon.db'
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

def get_ydl_items(status, schedule):

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    params = (status, schedule)

    cur.execute(
        "SELECT i.id, i.status, i.schedule, i.title, i.uploader, r.type AS r_type, r.title AS r_title, r.uploader AS r_uploader FROM ydl_item i INNER JOIN ydl_request r ON i.request_id = r.id WHERE i.status <= ? AND i.schedule >= ?", params)

    rows = cur.fetchall()

    items = []

    for row in rows:
        item = {'id': row[0], 'status': row[1], 'schedule': row[2], 'title': row[3], 'uploader': row[4], 'r_type': row[5], 'r_title': row[6], 'r_uploader': row[7]}
        items.append(item)
        print('item: \n\t', item)

    cur.close()
    conn.close()

    return items

def get_next_ydl_items(status, schedule, count):

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    params = (status, schedule, count)

    cur.execute(
        "SELECT i.id, i.status, i.schedule, i.title, i.uploader, r.type AS r_type, r.title AS r_title, r.uploader AS r_uploader FROM ydl_item i INNER JOIN ydl_request r ON i.request_id = r.id WHERE i.status <= ? AND i.schedule >= ? LIMIT ?", params)

    rows = cur.fetchall()

    items = []

    for row in rows:
        item = {'id': row[0], 'status': row[1], 'schedule': row[2], 'title': row[3], 'uploader': row[4], 'r_type': row[5], 'r_title': row[6], 'r_uploader': row[7]}
        items.append(item)

    cur.close()
    conn.close()

    return items

def get_ydl_items_by_request(request_id):

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    params = (request_id,)

    cur.execute(
        "SELECT id, title, status, progress, uploader FROM ydl_item WHERE request_id = ?", params)

    rows = cur.fetchall()

    items = []

    for row in rows:
        item = {'id': row[0], 'title': row[1],
                'status': row[2], 'progress': row[3], 'uploader': row[4]}
        items.append(item)

    cur.close()
    conn.close()

    return items


def get_ydl_requests():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT url, schedule, id, type, title, uploader FROM ydl_request")
    request_rows = cur.fetchall()

    requests = []

    for row in request_rows:
        items = get_ydl_items_by_request(row[2])
        sum_pgr, avg_pgr = 0, 0
        sum_sts, avg_sts = 0, 0
        for item in items:
            sum_pgr += item['progress']
            sum_sts += item['status']

        if len(items) > 0:
            avg_pgr = sum_pgr / len(items)
            avg_sts = sum_sts / len(items)

        request = {'id': row[2], 'url': row[0], 'schedule': row[1], 'type': row[3], 'title': row[4], 'uploader': row[5],
                   'items': items,'status': avg_sts, 'progress': avg_pgr}
        requests.append(request)
        # print(request)

    cur.close()
    conn.close()

    return requests


def get_ydl_request(id):
    conn = sqlite3.connect(DB_FILE)
    params = (id,)
    cur = conn.cursor()
    cur.execute("SELECT url, schedule, id, type, title, uploader FROM ydl_request WHERE id = ?", params)
    row = cur.fetchone()

    request = {'url': row[0], 'schedule': row[1], 'type': row[3], 'title': row[4], 'uploader': row[5],
               'items': get_ydl_items_by_request(row[2])}
    print(request)

    cur.close()
    conn.close()

    return request


def delete_ydl_request(id):
    conn = sqlite3.connect(DB_FILE)
    params = (id,)

    conn.execute("DELETE FROM ydl_item WHERE request_id = ?", params)
    conn.execute("DELETE FROM ydl_request WHERE id = ?", params)

    conn.commit()
    conn.close()

def delete_complete_requests():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute('SELECT request_id FROM (SELECT request_id, avg(status) AS avg_status FROM ydl_item GROUP BY request_id) WHERE avg_status = 3')

    rows = cur.fetchall()

    cur.close()

    for row in rows:
        params = (row[0],)
        conn.execute("DELETE FROM ydl_item WHERE request_id = ?", params)
        conn.execute("DELETE FROM ydl_request WHERE id = ?", params)

    conn.commit()
    conn.close()

def queue_video(video, request):
    print('{id:\'%s\', title:\'%s\'}' % (video['id'], video['title']))

    print('Play List: %s' %(video['playlist']))

    if video['playlist'] is not None:
        print('Uploader: %s' %(video['playlist_uploader']))
        print('Index in Playlist: %s' %(video['playlist_index']))

    conn = sqlite3.connect(DB_FILE)
    params = (video['id'], video['title'],
              request['schedule'], 0, 0, request['id'], video['uploader'])

    try:
        with conn:
            conn.execute(
                "INSERT INTO ydl_item(id, title, schedule, status, progress, request_id, uploader) VALUES (?,?,?,?,?,?,?)", params)
            conn.commit()
    except sqlite3.IntegrityError:
        print("video is already queued")

    conn.close()


def queue_video_list(videos, request):
    for video in videos:
        queue_video(video, request)


def resolve_items(request):

    ydl_opts = {
        'ignoreerrors': True,
        'quiet': True
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:

        result = ydl.extract_info(request['url'], download=False)
        _type = 'video' if (result.get('_type') is None) else result.get('_type')

        print('title:', result['title'])
        print('uploader:', result['uploader'])
        print('type:', _type)
    
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        params = (result['title'], result['uploader'], _type, request['id'])
        cur.execute(
            "UPDATE ydl_request SET title=?, uploader=?, type=? WHERE id=?", params)
        conn.commit()
        conn.close()

        if _type == 'video':
            print('###single video###')
            queue_video(result, request)

        elif _type == 'playlist':
            print("###playlist###")
            queue_video_list(result['entries'], request)

def queue_request(url, schedule):
    conn = sqlite3.connect(DB_FILE)
    print('Queuing the request url:%s, schedule:%d' % (url, schedule))
    cur = conn.cursor()
    params = (url, schedule)
    cur.execute(
        "INSERT INTO ydl_request(url, schedule) VALUES(?,?)", params)
    last_row_id = cur.lastrowid

    conn.commit()
    conn.close()
    return {'id': last_row_id, 'url': url, 'schedule': schedule}


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
        return jsonify(get_ydl_requests())

    @app.route('/api/requests/<int:id>', methods=['GET'])
    def get_request(id):
        return jsonify(get_ydl_request(id))

    @app.route('/api/requests/<int:id>', methods=['DELETE'])
    def delete_request(id):
        delete_ydl_request(id)
        return jsonify()

    @app.route('/api/requests', methods=['DELETE'])
    def clean_completed_requests():
        delete_complete_requests()
        return jsonify()

    @app.route('/api/requests', methods=['POST'])
    def add_request():
        content = request.json
        schedule = int(content.get('schedule', 0))
        url = content.get('url', None)

        if url is None:
            return jsonify(''), 400

        req = queue_request(url, schedule)
        resolver_thread = threading.Thread(target=resolve_items, args=(req,))
        resolver_thread.start()
        return jsonify(req), 201

    @app.route('/api/items', methods=['GET'])
    def get_items():
        return jsonify(get_ydl_items(3, 1))

    if __name__ == '__main__':
        app.run(host='0.0.0.0', debug=False)


def update_item_progress(filename, status, progress=0):
    filename_no_ext = os.path.splitext(filename)[0]
    filename_length = len(filename_no_ext)
    id = filename_no_ext[filename_length - YOUTUBE_VIDEO_ID_LENGTH : filename_length]
    conn = sqlite3.connect(DB_FILE)
    print('id:%s, status:%d, progress:%d' % (id, status, progress))
    cur = conn.cursor()
    params = (status, progress, id)
    cur.execute(
        "UPDATE ydl_item SET status=?, progress=? WHERE id=?", params)
    conn.commit()
    conn.close()


def status_hook(d):

    if d['status'] == 'downloading':
        progress = d['downloaded_bytes']/d['total_bytes']*100
        update_item_progress(d['filename'], 1, progress)
        print(round(progress, 1), '%')

    elif d['status'] == 'finished':
        update_item_progress(d['filename'], 3, 100)

    elif d['status'] == 'error':
        update_item_progress(d['filename'], -1)

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

        items = get_next_ydl_items(2, not is_off_peak, 1)

        ydl_opts = {
            'format': 'best',
            'progress_hooks': [status_hook]
        }

        for item in items:
            url = "https://www.youtube.com/watch?v=" + item['id']

            if item['r_type'] == 'video':
                ydl_opts['outtmpl'] = download_dir + '/%(title)s [%(uploader)s]-%(id)s.%(ext)s'
            else:
                dir_name = '{playlist} [{uploader}]'.format(uploader=clean_string(item['r_uploader']), playlist=clean_string(item['r_title']))
                ydl_opts['outtmpl'] = download_dir + '/' + dir_name + '/%(title)s - %(id)s.%(ext)s'

            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        time.sleep(10)


try:
    downloader_thread = threading.Thread(target=run_downloader)
    downloader_thread.start()
except:
    print('error starting the download server')

# with daemon.DaemonContext:
run_web_server()
