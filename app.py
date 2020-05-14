#! /usr/bin/python3

from __future__ import unicode_literals
from flask import Flask, jsonify, request
import youtube_dl
import threading
import sqlite3
import os
import datetime
import time
import sys

YOUTUBE_VIDEO_ID_LENGTH = 11

DB_FILE = sys.argv[1]


def get_ydl_items(status, schedule):

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    params = (status, schedule)

    cur.execute(
        "SELECT id, status, schedule FROM ydl_item WHERE status <= ? AND schedule >= ?", params)

    rows = cur.fetchall()

    items = []

    for raw in rows:
        item = {'id': raw[0], 'status': raw[1], 'schedule': raw[2]}
        items.append(item)
        print(item)

    cur.close()
    conn.close()

    return items


def get_ydl_items_by_request(request_id):

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    params = (request_id,)

    cur.execute(
        "SELECT id, title, status, progress FROM ydl_item WHERE request_id = ?", params)

    rows = cur.fetchall()

    items = []

    for raw in rows:
        item = {'id': raw[0], 'title': raw[1],
                'status': raw[2], 'progress': raw[3]}
        items.append(item)

    cur.close()
    conn.close()

    return items


def get_ydl_requests():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT url, schedule, id FROM ydl_request")
    request_rows = cur.fetchall()

    requests = []

    for raw in request_rows:
        request = {'id': raw[2], 'url': raw[0], 'schedule': raw[1],
                   'items': get_ydl_items_by_request(raw[2])}
        requests.append(request)
        print(request)

    cur.close()
    conn.close()

    return requests


def get_ydl_request(id):
    conn = sqlite3.connect(DB_FILE)
    params = (id,)
    cur = conn.cursor()
    cur.execute("SELECT url, schedule, id FROM ydl_request WHERE id = ?", params)
    raw = cur.fetchone()

    request = {'url': raw[0], 'schedule': raw[1],
               'items': get_ydl_items_by_request(raw[2])}
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

def queue_video(video, request):
    print('{id:\'%s\', title:\'%s\'}' % (video['id'], video['title']))

    conn = sqlite3.connect(DB_FILE)
    params = (video['id'], video['title'],
              request['schedule'], 0, 0, request['id'])

    try:
        with conn:
            conn.execute(
                "INSERT INTO ydl_item(id, title, schedule, status, progress, request_id) VALUES (?,?,?,?,?,?)", params)
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

        if result.get('_type') is None:
            print('###single video###')
            queue_video(result, request)

        elif result.get('_type') == 'playlist':
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

    app = Flask(__name__)

    @app.route('/')
    def index():
        return "Hello, World!"

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


def isNowInTimePeriod(startTime, endTime, nowTime):
    if startTime < endTime:
        return startTime <= nowTime <= endTime
    else:  # Over midnight
        return nowTime >= startTime or nowTime <= endTime


def run_downloader():

    from pathlib import Path
    DOWNLOAD_DIR = os.getcwd()

    print("Starting the download server ...")

    off_peak_start = datetime.time(0, 0)
    off_peak_end = datetime.time(8, 0)

    print("===== CONFIGS =====")
    print('Download Directory: %s' % (DOWNLOAD_DIR))
    print('Off Peak Schedule: %s - %s' % (off_peak_start, off_peak_end))
    print('===================')

    while True:
        time_now = datetime.datetime.now().time()
        is_off_peak = isNowInTimePeriod(
            off_peak_start, off_peak_end, time_now)

        schedule_text = 'Off Peak' if is_off_peak else 'Peak'

        print('Current Schedule: {}'.format(schedule_text))

        items = get_ydl_items(2, not is_off_peak)

        ydl_opts = {
            'format': 'best',
            'progress_hooks': [status_hook],
            'outtmpl': DOWNLOAD_DIR + '/%(title)s-%(id)s.%(ext)s'
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
