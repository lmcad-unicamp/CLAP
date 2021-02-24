GREEN='\033[0;32m'
NC='\033[0m'

function green_print(){
  printf "${GREEN}$1${NC}\n"
}

function abort() {
	echo "Error: $1"
	exit 1
}

CLAP_PATH=~/.clap

echo -n "Pulling repository for updates... "
date
git checkout master
git pull
echo "OK"

source clap-env/bin/activate || abort "Activating venv"
green_print "Updating clap...."
pip --no-cache-dir install . || abort "Updating clap..."
green_print "OK"

green_print "Updating CLAP path: $CLAP_PATH"
cp -r -n ./share/configs/ $CLAP_PATH
cp -r ./share/groups/ $CLAP_PATH
cp -r ./share/modules/ $CLAP_PATH
green_print "OK"
