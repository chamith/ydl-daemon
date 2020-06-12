
import sqlite3
import youtube_dl

DB_FILE=None

def init(db_file):
    global DB_FILE
    DB_FILE=db_file

def get_items(status, schedule):

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    params = (status, schedule)

    cur.execute(
        "SELECT i.id, i.status, i.schedule, i.title, i.uploader, r.type AS r_type, r.title AS r_title, r.uploader AS r_uploader FROM item i INNER JOIN request r ON i.request_id = r.id WHERE i.status <= ? AND i.schedule >= ?", params)

    rows = cur.fetchall()

    items = []

    for row in rows:
        item = {'id': row[0], 'status': row[1], 'schedule': row[2], 'title': row[3], 'uploader': row[4], 'r_type': row[5], 'r_title': row[6], 'r_uploader': row[7]}
        items.append(item)
        print('item: \n\t', item)

    cur.close()
    conn.close()

    return items

def get_next_items(status, schedule, count):

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    params = (status, schedule, count)

    cur.execute(
        "SELECT i.id, i.status, i.schedule, i.title, i.uploader, r.type AS r_type, r.title AS r_title, r.uploader AS r_uploader FROM item i INNER JOIN request r ON i.request_id = r.id WHERE i.status <= ? AND i.schedule >= ? LIMIT ?", params)

    rows = cur.fetchall()

    items = []

    for row in rows:
        item = {'id': row[0], 'status': row[1], 'schedule': row[2], 'title': row[3], 'uploader': row[4], 'r_type': row[5], 'r_title': row[6], 'r_uploader': row[7]}
        items.append(item)

    cur.close()
    conn.close()

    return items

def get_items_by_request(request_id):

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    params = (request_id,)

    cur.execute(
        "SELECT id, title, status, progress, uploader FROM item WHERE request_id = ?", params)

    rows = cur.fetchall()

    items = []

    for row in rows:
        item = {'id': row[0], 'title': row[1],
                'status': row[2], 'progress': row[3], 'uploader': row[4]}
        items.append(item)

    cur.close()
    conn.close()

    return items


def get_requests():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT url, schedule, id, type, title, uploader FROM request")
    request_rows = cur.fetchall()

    requests = []

    for row in request_rows:
        items = get_items_by_request(row[2])
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


def get_request(id):
    conn = sqlite3.connect(DB_FILE)
    params = (id,)
    cur = conn.cursor()
    cur.execute("SELECT url, schedule, id, type, title, uploader FROM request WHERE id = ?", params)
    row = cur.fetchone()

    request = {'url': row[0], 'schedule': row[1], 'type': row[3], 'title': row[4], 'uploader': row[5],
               'items': get_items_by_request(row[2])}
    print(request)

    cur.close()
    conn.close()

    return request


def delete_request(id):
    conn = sqlite3.connect(DB_FILE)
    params = (id,)

    conn.execute("DELETE FROM item WHERE request_id = ?", params)
    conn.execute("DELETE FROM request WHERE id = ?", params)

    conn.commit()
    conn.close()

def delete_complete_requests():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute('SELECT request_id FROM (SELECT request_id, avg(status) AS avg_status FROM item GROUP BY request_id) WHERE avg_status = 3')

    rows = cur.fetchall()

    cur.close()

    for row in rows:
        params = (row[0],)
        conn.execute("DELETE FROM item WHERE request_id = ?", params)
        conn.execute("DELETE FROM request WHERE id = ?", params)

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
                "INSERT INTO item(id, title, schedule, status, progress, request_id, uploader) VALUES (?,?,?,?,?,?,?)", params)
            conn.commit()
    except sqlite3.IntegrityError:
        print("video is already queued")

    conn.close()


def queue_video_list(videos, request):
    for video in videos:
        queue_video(video, request)


def resolve_items(request):

    opts = {
        'ignoreerrors': True,
        'quiet': True
    }

    with youtube_dl.YoutubeDL(opts) as ydl:

        result = ydl.extract_info(request['url'], download=False)
        _type = 'video' if (result.get('_type') is None) else result.get('_type')

        print('title:', result['title'])
        print('uploader:', result['uploader'])
        print('type:', _type)
    
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        params = (result['title'], result['uploader'], _type, request['id'])
        cur.execute(
            "UPDATE request SET title=?, uploader=?, type=? WHERE id=?", params)
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
        "INSERT INTO request(url, schedule) VALUES(?,?)", params)
    last_row_id = cur.lastrowid

    conn.commit()
    conn.close()
    return {'id': last_row_id, 'url': url, 'schedule': schedule}

def update_item_progress(filename, status, progress=0):
    filename_no_ext = os.path.splitext(filename)[0]
    filename_length = len(filename_no_ext)
    id = filename_no_ext[filename_length - YOUTUBE_VIDEO_ID_LENGTH : filename_length]
    conn = sqlite3.connect(DB_FILE)
    print('id:%s, status:%d, progress:%d' % (id, status, progress))
    cur = conn.cursor()
    params = (status, progress, id)
    cur.execute(
        "UPDATE item SET status=?, progress=? WHERE id=?", params)
    conn.commit()
    conn.close()