#! /bin/bash

SVC_NAME=doda
SRC_NAME=app.py
SCRIPT_DIR=$(dirname "$0")
LIB_DIR=/var/lib/$SVC_NAME
SVC_DIR=/etc/systemd/system
BIN_FILE_TARGET=$LIB_DIR/$SRC_NAME

git pull origin master

if [ -f "$SVC_DIR/$SVC_NAME.service" ]; then
    echo "Stopping the service $SVC_NAME"
    systemctl stop $SVC_NAME

    echo "Updating the binaries"
    cp $SCRIPT_DIR/*.py $LIB_DIR/

    echo "Updating the web ui files"
    rm $LIB_DIR/web-ui -r
    cp $SCRIPT_DIR/web-ui $LIB_DIR/ -r

    echo "Starting the service $SVC_NAME"
    systemctl start $SVC_NAME
fi