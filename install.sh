#!/bin/bash

GREEN='\033[0;32m'
NC='\033[0m'

function green_print(){
  printf "${GREEN}$1${NC}\n"
}

CLAP_PATH=~/.clap

function abort() {
	echo "Error: $1"
	exit 1
}

green_print "Creating clap's virtualenv..."
python3 -m venv clap-env || abort "Creating venv"
echo "export CLAP=$PWD" >> clap-env/bin/activate || abort "Error writing on activate"
echo "export CLAP_PATH=$CLAP_PATH" >> clap-env/bin/activate || abort "Error writing on activate"
echo "export PATH=\$PATH:$PWD" >> clap-env/bin/activate || abort "Error writing on activate"
source clap-env/bin/activate || abort "Activating venv"
green_print "OK"

green_print "Upgrading PIP..."
pip install --upgrade 'pip>=9.0.0' || abort "Upgrading PIP"
green_print "OK"

green_print "Installing clap's requirements...."
pip install -r requirements.txt || abort "Installing clap requirements..."
green_print "OK"

# echo 'eval "$(register-python-argcomplete clapp)"' >> clap-env/bin/activate || abort "Error writting on activate"

green_print "Creating default folders"
green_print "Using default CLAP path: $CLAP_PATH"
mkdir -p $CLAP_PATH/configs/
mkdir -p $CLAP_PATH/configs/clusters/
mkdir -p $CLAP_PATH/roles/
mkdir -p $CLAP_PATH/private/
mkdir -p $CLAP_PATH/storage/
cp -r -n ./share/configs/ $CLAP_PATH
cp -r ./share/roles/ $CLAP_PATH

green_print "OK"
green_print "Use: 'source ./clap-env/bin/activate' to use CLAP"
