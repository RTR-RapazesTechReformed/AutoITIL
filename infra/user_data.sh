#!/usr/bin/env bash
# Bootstrap da EC2 no primeiro boot: Docker Engine + plugin compose, cliente
# psql, swap e a pasta do app. NAO clona nem sobe a aplicacao — o repositorio
# e privado; o codigo chega por scripts/deploy.* e e construido la.
# Log completo em /var/log/cloud-init-output.log.
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl postgresql-client python3

# Docker Engine + plugin compose (repositorio oficial)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
usermod -aG docker ubuntu

# Swap de 4 GB: rede de seguranca para o enriquecimento com Gemma na CPU.
if [ ! -f /swapfile ]; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

install -d -o ubuntu -g ubuntu -m 0755 /opt/autoitil

# Sinaliza para o scripts/deploy.* que a maquina esta pronta. Sempre por ultimo.
touch /opt/autoitil/.bootstrap-done
chown ubuntu:ubuntu /opt/autoitil/.bootstrap-done
