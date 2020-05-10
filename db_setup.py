#! /usr/bin/python3

import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1])
conn.execute("CREATE TABLE 'ydl_item' ('id'	TEXT, 'title' INTEGER, 'schedule' INTEGER, 'status'	INTEGER, 'progress'	INTEGER,'request_id' INTEGER)")
conn.execute("CREATE TABLE 'ydl_request' ('id'	INTEGER, 'url' TEXT, 'type' INTEGER, 'schedule' INTEGER, 'status' INTEGER)")
conn.commit()
conn.close()