#! /bin/bash

SVC_NAME=youtube-dl-daemon
SRC_NAME=app.py
SCRIPT_DIR=$(dirname "$0")
BIN_DIR=/usr/local/bin
LIB_DIR=/var/lib/$SVC_NAME
SVC_DIR=/etc/systemd/system
DB_NAME=$SVC_NAME.db
BIN_FILE_TARGET=$BIN_DIR/$SVC_NAME
DB_FILE_TARGET=$LIB_DIR/$DB_NAME

if [ -z "$1" ]; then
    echo "please specify the download directory"
    exit 1
fi

DL_DIR=$1

if [ -f "$BIN_FILE_TARGET" ]; then
    echo "removing existing binary files"
    rm $BIN_FILE_TARGET
fi

cp $SCRIPT_DIR/$SRC_NAME $BIN_FILE_TARGET

if [ ! -d "$LIB_DIR" ]; then
    echo "creating the lib directory"
    mkdir $LIB_DIR
fi

if [ -f "$LIB_DIR/$DB_NAME" ]; then
    echo "removing the db"
    rm $LIB_DIR/$DB_NAME
fi

echo "creating the db"
$SCRIPT_DIR/db_setup.py $LIB_DIR/$DB_NAME

if [ ! -d "$DL_DIR" ]; then
    mkdir $DL_DIR
fi

apt install python3-pip -y
pip3 install -r $SCRIPT_DIR/requirements.txt

if [ -f "$SVC_DIR/$SVC_NAME.service" ]; then
    echo "removing the existing service file"
    systemctl stop $SVC_NAME
    systemctl disable $SVC_NAME.service
    rm $SVC_DIR/$SVC_NAME.service
fi

echo "installing the new service"
cat $SCRIPT_DIR/service.tmpl | sed "s^SVC_NAME^$SVC_NAME^g" | sed "s^BIN_FILE_TARGET^$BIN_FILE_TARGET^g" | sed "s^DB_FILE_TARGET^$DB_FILE_TARGET^g"  | sed "s^DL_DIR^$DL_DIR^g"  > $SVC_DIR/$SVC_NAME.service

systemctl daemon-reload
systemctl enable $SVC_NAME.service
systemctl start $SVC_NAME
systemctl status $SVC_NAME
