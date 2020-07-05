#!/bin/sh
while [ "x$(sudo lsof /var/lib/dpkg/lock-frontend)" != "x" ] ; do
    sleep 30
done
cd /tmp
wget https://lmcad-zabbix-agent.s3.us-east-2.amazonaws.com/zabbix-agent.deb
wget https://lmcad-zabbix-agent.s3.us-east-2.amazonaws.com/zabbix-server-ip
SERVER_IP=$(cat zabbix-server-ip)
SERVER_TOKEN="755730f39f40c601b801f3f21a7187359a46c6d6917ce14e1bc7ac426b830a63-lmcad"
CONFIGURATION_FILE="/etc/zabbix/zabbix_agentd.conf"
sudo dpkg --force-all -i zabbix-agent.deb
sudo apt-get update
sudo apt-get install zabbix-agent
wget https://lmcad-zabbix-agent.s3.us-east-2.amazonaws.com/zabbix-configuration.sh
sh zabbix-configuration.sh $SERVER_IP $SERVER_TOKEN $CONFIGURATION_FILE
sudo systemctl restart zabbix-agent
sudo systemctl enable zabbix-agent
