#! /bin/bash

SVC_NAME=youtube-dl-daemon
SRC_NAME=app.py
SCRIPT_DIR=$(dirname "$0")
BIN_DIR=/usr/local/bin
SVC_DIR=/etc/systemd/system
BIN_FILE_TARGET=$BIN_DIR/$SVC_NAME


if [ -f "$SVC_DIR/$SVC_NAME.service" ]; then
    echo "Stopping the service $SVC_NAME"
    systemctl stop $SVC_NAME

    echo "Updating the binaries"
    cp $SCRIPT_DIR/$SRC_NAME $BIN_FILE_TARGET

    echo "Starting the service $SVC_NAME"
    systemctl start $SVC_NAME
fi