# Install elasticluster and their dependencies

function abort() {
	echo "Error: $1"
	exit 1
}

echo "Installing dependencies...."
sudo apt-get update
sudo apt-get install -y gcc g++ git libc6-dev libffi-dev libssl-dev python3-dev virtualenv python3 python3-pip || abort "Executing apt command"
echo "OK"

CLAP_PATH=~/.clap

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
cd downloads

echo "Fetching elasticluster"
if [[ ! -d elasticluster ]]; then
  git clone git://github.com/gc3-uzh-ch/elasticluster.git elasticluster || abort "Fetching elasticluster"
fi
cd elasticluster
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

echo "OK"
