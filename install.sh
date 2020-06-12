#! /bin/bash

SVC_NAME=doda
SRC_NAME=app.py
SCRIPT_DIR=$(dirname "$0")
LIB_DIR=/var/lib/$SVC_NAME
SVC_DIR=/etc/systemd/system
DB_NAME=$SVC_NAME.db
CONF_NAME=$SVC_NAME.conf
BIN_FILE_TARGET=$LIB_DIR/$SVC_NAME
DB_FILE_TARGET=$LIB_DIR/$DB_NAME
CONF_FILE_TARGET=$LIB_DIR/$CONF_NAME

if [ ! -d "$LIB_DIR" ]; then
    echo "creating the lib directory"
    mkdir $LIB_DIR
fi

if [ -f "$BIN_FILE_TARGET" ]; then
    echo "removing existing binary files"
    rm $BIN_FILE_TARGET
fi

cp $SCRIPT_DIR/$SRC_NAME $BIN_FILE_TARGET

if [ -f "$LIB_DIR/$DB_NAME" ]; then
    echo "removing the db"
    rm $LIB_DIR/$DB_NAME
fi

if [ -d "$LIB_DIR" ]; then
    echo "copying the web ui files"
    cp $SCRIPT_DIR/web-ui $LIB_DIR/ -r
fi
echo "creating the db"
$SCRIPT_DIR/db_setup.py $LIB_DIR/$DB_NAME

echo "copying the config file"
cp $SCRIPT_DIR/$CONF_NAME $CONF_FILE_TARGET

apt install python3-pip -y
pip3 install -r $SCRIPT_DIR/requirements.txt

if [ -f "$SVC_DIR/$SVC_NAME.service" ]; then
    echo "removing the existing service file"
    systemctl stop $SVC_NAME
    systemctl disable $SVC_NAME.service
    rm $SVC_DIR/$SVC_NAME.service
fi

echo "installing the new service"
cat $SCRIPT_DIR/service.tmpl | sed "s^SVC_NAME^$SVC_NAME^g" | sed "s^LIB_DIR^$LIB_DIR^g" | sed "s^BIN_FILE_TARGET^$BIN_FILE_TARGET^g" | sed "s^DB_FILE_TARGET^$DB_FILE_TARGET^g"  | sed "s^CONF_FILE_TARGET^$CONF_FILE_TARGET^g"  > $SVC_DIR/$SVC_NAME.service

systemctl daemon-reload
systemctl enable $SVC_NAME.service
systemctl start $SVC_NAME
systemctl status $SVC_NAME
