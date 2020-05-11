#! /usr/bin/python3

from __future__ import unicode_literals
import youtube_dl
import threading
import sqlite3
from flask import Flask, jsonify, request
import os
import datetime
import time
import sys

DB_FILE = sys.argv[1]


def get_ydl_requests():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT url, status, schedule FROM ydl_request")
    request_rows = cur.fetchall()

    requests = []

    for raw in request_rows:
        request = {'url': raw[0], 'status': raw[1], 'schedule': raw[2]}
        requests.append(request)
        print(request)

    cur.close()
    conn.close()

    return requests


def get_ydl_items(status, schedule):

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    params = (status, schedule)

    cur.execute("SELECT id, status, schedule FROM ydl_item WHERE status <= ? AND schedule <= ?", params)

    rows = cur.fetchall()

    items = []

    for raw in rows:
        item = {'id': raw[0], 'status': raw[1], 'schedule': raw[2]}
        items.append(item)
        print(item)

    cur.close()
    conn.close()

    return items


def queue_video(video, request):
    print('{id:\'%s\', title:\'%s\'}' % (video['id'], video['title']))

    conn = sqlite3.connect(DB_FILE)
    params = (video['id'], video['title'],
              request['schedule'], 0, 0, request['id'])
    conn.execute(
        "INSERT INTO ydl_item(id, title, schedule, status, progress, request_id) VALUES (?,?,?,?,?,?)", params)
    conn.commit()
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

        if result.get('_type') is None:
            print('###single video###')
            queue_video(result, request)

        elif result.get('_type') == 'playlist':
            print("###playlist###")
            queue_video_list(result['entries'], request)


def queue_request(url, schedule):
    conn = sqlite3.connect(DB_FILE)
    print('url:%s, schedule:%d' % (url, schedule))
    cur = conn.cursor()
    params = (url, schedule, 0)
    cur.execute(
        "INSERT INTO ydl_request(url, schedule, status) VALUES(?,?,?)", params)
    last_row_id = cur.lastrowid

    conn.commit()
    conn.close()
    return {'id': last_row_id, 'url': url, 'schedule': schedule}


def run_web_server():

    app = Flask(__name__)

    @app.route('/')
    def index():
        return "Hello, World!"

    @app.route('/requests', methods=['GET'])
    def get_requests():
        return jsonify(get_ydl_requests())

    @app.route('/requests', methods=['POST'])
    def add_request():
        content = request.json
        schedule = content.get('schedule', 0)

        req = queue_request(content['url'], schedule)
        resolver_thread = threading.Thread(target=resolve_items, args=(req,))
        resolver_thread.start()
        return jsonify(req), 201

    @app.route('/items', methods=['GET'])
    def get_items():
        return jsonify(get_ydl_items(3, 1))

    if __name__ == '__main__':
        app.run(host='0.0.0.0', debug=False)


def update_item_progress(filename, status, progress=0):
    filename_no_ext = os.path.splitext(filename)[0]
    lst = filename_no_ext.split('-')
    id = lst[len(lst)-1]
    conn = sqlite3.connect(DB_FILE)
    print('id:%s, status:%d, progress:%d' % (id, status, progress))
    cur = conn.cursor()
    params = (status, progress, id)
    cur.execute(
        "UPDATE ydl_item SET status=?, progress=? WHERE id=?", params)
    conn.commit()
    conn.close()


def status_hook(d):

    print('filename:%s, status:%s' % (d['filename'], d['status']))
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


def run_downloader():

    print("Starting the download server ...")

    off_peak_start = datetime.time(0, 0)
    off_peak_end = datetime.time(8, 0)

    print("===== CONFIGS =====")
    print('Download Directory: %s' %(os.getcwd()))
    print('Off Peak Schedule: %s - %s' %(off_peak_start , off_peak_end))
    print('===================')

    while True:
        time_now = datetime.datetime.now().time()
        schedule = off_peak_start < time_now and time_now < off_peak_end
        # false (0): offpeak
        # true  (1): anytime

        items = get_ydl_items(2, schedule)

        ydl_opts = {
            'progress_hooks': [status_hook]
        }

        for item in items:
            url = "https://www.youtube.com/watch?v=" + item['id']

            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        time.sleep(60)


try:
    downloader_thread = threading.Thread(target=run_downloader)
    downloader_thread.start()
except:
    print('error starting the download server')

# with daemon.DaemonContext:
run_web_server()
