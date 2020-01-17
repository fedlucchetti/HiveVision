#!/usr/bin/env bash

echo "Bringing the composition down..."
cd ..

docker-compose down
sleep 10
ACTVOL=$(docker volume ls -q)
ACTCONT=$(docker image ls -q)

if [ -n "$ACTCONT" ]
then
  docker rmi -f $ACTCONT
else
    echo "No containers found."
fi


if [ -n "$ACTVOL" ]
then
  docker volume rm $ACTVOL
else
    echo "No volumes found."
fi

echo "Removing the stores."
sudo rm -rf /mongostore /redisstore

echo "Checking up."
docker images -q
docker volume ls -q