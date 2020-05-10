#! /bin/bash

SCRIPT_DIR=$(dirname "$0")
BIN_DIR=/usr/local/bin
LIB_DIR=/var/lib/ydl-daemon
SVC_DIR=/etc/systemd/system
SVC_NAME=ydl-daemon
DB_NAME=ydl-daemon.db

cp $SCRIPT_DIR/ydl-daemon.py $BIN_DIR/
mkdir $LIB_DIR
cp $SCRIPT_DIR/service.tmpl $SVC_DIR/$SVC_NAME.service
$SCRIPT_DIR/db_setup.py $LIB_DIR/$DB_NAME

pip install -r $SCRIPT_DIR/requirements.txt
systemctl daemon-reload
systemctl enable $SVC_NAME.service
systemctl start $SVC_NAME
systemctl status $SVC_NAME