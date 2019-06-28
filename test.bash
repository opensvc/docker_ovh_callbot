#!/bin/bash

docker run --env-file test.envfile -it opensvc/ovh_callbot:latest 
