#! /usr/bin/python3

from __future__ import unicode_literals
import youtube_dl
import threading
import sqlite3
from flask import Flask, jsonify, request

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

def get_ydl_items():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT id, status, schedule FROM ydl_item")
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
        req = queue_request(content['url'], content['schedule'])
        resolver_thread = threading.Thread(target=resolve_items, args=(req,))
        resolver_thread.start()
        return jsonify(req), 201

    if __name__ == '__main__':
        app.run(host='0.0.0.0', debug=True)


def status_hook(d):
    print(d)
    if d['status'] == 'downloading':
        print('in-progress')
        progress = d['downloaded_bytes']/d['total_bytes']*100
        print(round(progress, 1), '%')
    elif d['status'] == 'finished':
        print('complete')
    elif d['status'] == 'error':
        print('error')
    else:
        print('pending')


def run_downloader():
    
    print("starting the download server ...")

    items = get_ydl_items()



    ydl_opts = {
        'progress_hooks': [status_hook]
    }

    for item in items:
        url = "https://www.youtube.com/watch?v=" + item['id']
        print(url)
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])


try:
    #web_server_thread = threading.Thread(target=run_web_server)
    # web_server_thread.start()
    downloader_thread = threading.Thread(target=run_downloader)
    downloader_thread.start()
except:
    print('error starting the web server')

run_web_server()
