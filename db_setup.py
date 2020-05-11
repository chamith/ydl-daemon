#! /usr/bin/python3

import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1])
conn.execute("CREATE TABLE 'ydl_request' ('id'	INTEGER, 'url' TEXT, 'schedule' INTEGER, PRIMARY KEY ('id'))")
conn.execute("CREATE TABLE 'ydl_item' ('id'	TEXT, 'title' INTEGER, 'schedule' INTEGER, 'status'	INTEGER, 'progress'	INTEGER,'request_id' INTEGER, PRIMARY KEY ('id', 'request_id'))")
conn.commit()
conn.close()