#!/bin/bash

CLAP_PATH=~/.clap

echo -n "Pulling repository for updates... "
date
git pull
git checkout .
echo "OK"

echo "Using default CLAP path: $CLAP_PATH"

./install.sh
