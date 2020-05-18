#! /bin/bash

SVC_NAME=youtube-dl-daemon
SRC_NAME=app.py
SCRIPT_DIR=$(dirname "$0")
LIB_DIR=/var/lib/$SVC_NAME
SVC_DIR=/etc/systemd/system
BIN_FILE_TARGET=$LIB_DIR/$SVC_NAME


if [ -f "$SVC_DIR/$SVC_NAME.service" ]; then
    echo "Stopping the service $SVC_NAME"
    systemctl stop $SVC_NAME

    echo "Updating the binaries"
    cp $SCRIPT_DIR/$SRC_NAME $BIN_FILE_TARGET

    echo "Updating the web ui files"
    cp $SCRIPT_DIR/web-ui $LIB_DIR/ -r

    echo "Starting the service $SVC_NAME"
    systemctl start $SVC_NAME
fi