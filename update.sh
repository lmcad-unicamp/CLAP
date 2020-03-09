#!/bin/bash

CLAP_PATH=~/.clap

echo -n "Pulling repository for updates... "
date
git pull
git checkout .
echo "OK"

echo "Using default CLAP path: $CLAP_PATH"

echo -n "Copying new group files... "
cp -r ./share/groups/ $CLAP_PATH
echo "OK"

echo -n "Copying new module files... "
cp -r ./share/modules/ $CLAP_PATH
echo "OK"
