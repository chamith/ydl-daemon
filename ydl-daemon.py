#! /usr/bin/python3

from __future__ import unicode_literals
import youtube_dl
import threading
import sqlite3
from flask import Flask, jsonify, request
import os, time, datetime
import daemon

DB_FILE='ydl-daemon.db'

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

def get_ydl_items(status, off_peak):

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    params = (status,)

    if off_peak:
        print("getting all items")
        cur.execute("SELECT id, status, schedule FROM ydl_item WHERE status < ?", params)
    else:
        print("getting anytime items")
        cur.execute("SELECT id, status, schedule FROM ydl_item WHERE status < ? AND schedule = 1", params)
        
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
        return jsonify(get_ydl_items(4, True))

    if __name__ == '__main__':
        app.run(host='0.0.0.0', debug=False)

def update_item_progress(filename, status, progress=0):
    id = os.path.splitext(filename)[0].split('-')[1]
    conn = sqlite3.connect(DB_FILE)
    print('id:%s, status:%d, progress:%d' % (id, status, progress))
    cur = conn.cursor()
    params = (status, progress, id)
    cur.execute(
        "UPDATE ydl_item SET status=?, progress=? WHERE id=?", params)
    conn.commit()
    conn.close()

def status_hook(d):

    print('filename:%s, status:%s' %(d['filename'], d['status']))
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
    
    print("starting the download server ...")

    off_peak_start=datetime.time(0,0)
    off_peak_end=datetime.time(8,0)

    print('off-peak start:', off_peak_start)
    print('off-peak end:', off_peak_end)

    while True:

        print(datetime.datetime.now().time())
        
        if datetime.datetime.now().time() > off_peak_start and datetime.datetime.now().time() < off_peak_end :
            off_peak = True
            print ("running in the off peak mode")
        else:
            off_peak = False
            print ("running in the peak mode")

        items = get_ydl_items(3, off_peak)

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

#with daemon.DaemonContext:
run_web_server()
