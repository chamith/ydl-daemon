#! /usr/bin/python3

from __future__ import unicode_literals
import youtube_dl
import threading

def run_web_server():
    from flask import Flask

    app = Flask(__name__)

    @app.route('/')
    def index():
        return "Hello, World!"

    if __name__ == '__main__':
        app.run(host='0.0.0.0', debug=True)

def status_hook(d):
        if d['status'] == 'downloading':
                print('in-progress')
                progress = d['downloaded_bytes']/d['total_bytes']*100
                print(round(progress,1),'%')
        elif d['status'] == 'finished':
                print('complete')
        elif d['status'] == 'error':
                print('error')
        else:
                print('pending')

def run_downloader():
    ydl_opts = {
            'progress_hooks': [status_hook]
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download(['https://www.youtube.com/watch?v=BaW_jenozKc'])

try:
    #web_server_thread = threading.Thread(target=run_web_server)
    #web_server_thread.start()
    downloader_thread = threading.Thread(target=run_downloader)
    downloader_thread.start()
except:
    print('error starting the web server')
   
run_web_server()