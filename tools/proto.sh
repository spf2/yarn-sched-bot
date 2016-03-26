#!/bin/sh

PROTOS=/Users/spf/YN/bot-api/proto
PYOUT=proto

echo rm pyc
find $PYOUT -name '*.pyc' -exec rm -f {} \;

echo py
protoc -I $PROTOS $PROTOS/*.proto --python_out=$PYOUT

