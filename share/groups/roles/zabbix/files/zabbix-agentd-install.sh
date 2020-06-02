#!/bin/sh
cd /tmp
wget https://repo.zabbix.com/zabbix/4.2/ubuntu/pool/main/z/zabbix-release/zabbix-release_4.2-1+bionic_all.deb
sudo dpkg -i zabbix-release_4.2-1+bionic_all.deb
sudo apt-get update
sudo apt-get install zabbix-agent
#INSTANCEID=$(curl http://169.254.169.254/latest/meta-data/instance-id)
#sudo hostnamectl set-hostname $INSTANCEID
sudo sed -i "s/# Hostname=/Hostname=$(curl http://169.254.169.254/latest/meta-data/instance-id)/g" /etc/zabbix/zabbix_agentd.conf
sudo sed -i "s/Server=127.0.0.1/Server=3.134.81.21/g" /etc/zabbix/zabbix_agentd.conf
sudo sed -i "s/ServerActive=127.0.0.1/ServerActive=3.134.81.21/g" /etc/zabbix/zabbix_agentd.conf
sudo sed -i "/Hostname=Zabbix server/d" /etc/zabbix/zabbix_agentd.conf
sudo sed -i "s/# HostMetadata=/HostMetadata=t2.micro-755730f39f40c601b801f3f21a7187359a46c6d6917ce14e1bc7ac426b830a63-lmcad/g" /etc/zabbix/zabbix_agentd.conf
sudo sed -i "s/# EnableRemoteCommands=0/EnableRemoteCommands=1/g" /etc/zabbix/zabbix_agentd.conf
sudo systemctl restart zabbix-agent
sudo systemctl enable zabbix-agent

