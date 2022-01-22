#!/bin/bash

rsync -r ./* tg:/home/ubuntu/killer_bot -v --exclude='.idea/*'