#!/bin/bash

CLAP_PATH=~/.clap

function abort() {
	echo "Error: $1"
	exit 1
}

echo "Creating clap virtualenv..."
virtualenv -p python3 clap-env || abort "Creating venv"
echo "export CLAP=$PWD" >> clap-env/bin/activate || abort "Error writting on activate"
echo "export CLAP_PATH=$CLAP_PATH" >> clap-env/bin/activate || abort "Error writting on activate"
echo "export PATH=\$PATH:$PWD" >> clap-env/bin/activate || abort "Error writting on activate"
source clap-env/bin/activate || abort "Activating venv"
echo "OK"

echo "Upgrading PIP..."
pip install --upgrade 'pip>=9.0.0' || abort "Upgrading PIP"
echo "OK"

mkdir -p downloads
cd downloads || abort "Invalid directory downloads"

echo "Fetching elasticluster"
if [[ ! -d elasticluster ]]; then
  git clone -b v1.3.dev25 https://github.com/elasticluster/elasticluster.git elasticluster || abort "Fetching elasticluster"
fi
cd elasticluster || abort "Invalid directory elasticluster"
pip install -e . || abort "Installing elasticluster"
cd ../..
echo "OK"

echo "Installing clap requirements"
pip install -r requirements.txt || abort "Installing clap requirements"
echo "OK"

echo "Creating default folders"
echo "Using default CLAP path: $CLAP_PATH" 
mkdir -p $CLAP_PATH/configs/
mkdir -p $CLAP_PATH/modules/
mkdir -p $CLAP_PATH/groups/
mkdir -p $CLAP_PATH/private/
mkdir -p $CLAP_PATH/storage/
mkdir -p $CLAP_PATH/storage/clusters.d
cp -r ./share/configs/ $CLAP_PATH
cp -r ./share/groups/ $CLAP_PATH
cp -r ./share/modules/ $CLAP_PATH

echo "OK"
