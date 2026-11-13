#!/usr/bin/env bash
# Publica na EC2 o que esta COMMITADO (HEAD) neste repositorio. Rode na sua
# maquina, depois do "terraform apply", e de novo a cada mudanca de codigo:
#
#   bash infra/deploy.sh
#
# Le do infra/.env: HF_TOKEN, SSH_KEY (padrao: ~/Downloads/labsuser.pem),
# ADMIN_EMAIL e ADMIN_PASSWORD. Uma variavel de ambiente com o mesmo nome tem
# prioridade sobre o arquivo.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

die() { echo "ERRO: $*" >&2; exit 1; }
# Valor de uma chave: ambiente primeiro, depois infra/.env (a ultima ocorrencia).
cfg() {
  local v="${!1:-}"
  if [ -z "$v" ] && [ -f .env ]; then
    v=$(sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" .env | tail -1 | tr -d "\r\"'")
  fi
  printf '%s' "$v"
}

KEY=$(cfg SSH_KEY)
KEY="${KEY:-$HOME/Downloads/labsuser.pem}"
[ -f "$KEY" ] || die "chave SSH nao encontrada em $KEY. Ajuste SSH_KEY no infra/.env."

IP=$(terraform output -raw public_ip 2>/dev/null) && ENV=$(terraform output -raw deploy_env 2>/dev/null) \
  || die "sem os outputs do Terraform. Rode 'terraform -chdir=infra apply' antes."

HF=$(cfg HF_TOKEN)
[ -n "$HF" ] || die "preencha HF_TOKEN no infra/.env"

# Copia da chave com permissao restrita: o ssh recusa chave "aberta" demais.
mkdir -p .deploy
cp "$KEY" .deploy/key.pem
chmod 600 .deploy/key.pem
SSH_OPTS=(-i .deploy/key.pem -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=.deploy/known_hosts
          -o ConnectTimeout=10 -o ServerAliveInterval=30 -o LogLevel=ERROR)
rssh() { ssh "${SSH_OPTS[@]}" "ubuntu@$IP" "$@"; }

[ -z "$(git status --porcelain)" ] || echo "AVISO: ha alteracoes nao commitadas; so o que esta no HEAD e enviado."
# autocrlf desligado: no Windows o pacote sairia com CRLF e quebraria os scripts.
git -c core.autocrlf=false -C .. archive --format=tar -o infra/.deploy/app.tar HEAD \
  backend frontend db infra/docker-compose.aws.yml infra/remote-deploy.sh

echo "Aguardando a EC2 aceitar SSH e terminar o bootstrap (Docker)..."
for i in $(seq 120); do
  rssh 'test -f /opt/autoitil/.bootstrap-done' 2>/dev/null && break
  [ "$i" -lt 120 ] || die "a EC2 nao ficou pronta em 10 min. Seu IP mudou? Rode 'terraform -chdir=infra apply'."
  sleep 5
done

echo "Enviando $(git rev-parse --short HEAD) para ubuntu@$IP..."
scp -C "${SSH_OPTS[@]}" .deploy/app.tar "ubuntu@$IP:/opt/autoitil/app.tar"
# Os segredos vao pelo stdin do ssh para a RAM da EC2: nunca na linha de comando.
printf '%s\nHF_TOKEN=%s\nADMIN_EMAIL=%s\nADMIN_PASSWORD=%s\n' "$ENV" "$HF" "$(cfg ADMIN_EMAIL)" "$(cfg ADMIN_PASSWORD)" \
  | rssh 'umask 077; cat > /dev/shm/autoitil-input'
rssh 'cd /opt/autoitil && tar -xf app.tar --strip-components=1 infra/remote-deploy.sh && bash remote-deploy.sh start'

# Acompanha o log. Se o SSH cair (255), o deploy continua na EC2: reconecta.
from=+1
code=255
for _ in $(seq 30); do
  rssh "bash /opt/autoitil/remote-deploy.sh follow $from" && code=0 || code=$?
  [ "$code" -eq 255 ] || break
  echo "(conexao caiu, reconectando...)"
  from=20
  sleep 5
done
[ "$code" -eq 0 ] || die "o deploy falhou (codigo $code). Log na EC2: /opt/autoitil/deploy.log"

echo
echo "AutoITIL no ar: http://$IP"
