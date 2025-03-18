#!/usr/bin/env sh
# keep the container running, but allow it to be interruptable
# source: https://www.reddit.com/r/docker/comments/z4i7mz/comment/ixr6fs7
trap : TERM INT
sleep infinity &
wait
