#! /bin/bash

SVC_NAME=youtube-dl-daemon
LIB_DIR=/var/lib/$SVC_NAME
SVC_DIR=/etc/systemd/system

if [ -f "$SVC_DIR/$SVC_NAME.service" ]; then
    echo "removing the existing service file"
    systemctl stop $SVC_NAME
    systemctl disable $SVC_NAME.service
    rm $SVC_DIR/$SVC_NAME.service
fi

if [ -d "$LIB_DIR" ]; then
    echo "removing the library files"
    rm $LIB_DIR -r
fi
