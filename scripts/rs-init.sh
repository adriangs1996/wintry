#!/bin/bash

echo "Starting replica set initialization"
until mongosh --host mongo --eval "print(\"waited for connection\")"
do
   sleep 2
done

echo "Connection finished"
echo "Creating replica set"

MONGO1IP=$(getent hosts mongo | awk '{ print $1 }')

read -r -d '' CMD <<EOF
var config = {
    "_id": "dbrs",
    "version": 1,
    "members": [
        {
            "_id": 1,
            "host":'${MONGO1IP}:27017',
        }
    ]
};
rs.initiate(config, { force: true });
EOF

echo $CMD | mongosh --host mongo
echo "replica set created"