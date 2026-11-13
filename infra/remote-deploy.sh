#!/usr/bin/env bash
# Roda NA EC2, como o usuario ubuntu. Quem chama e o infra/deploy.* (da sua
# maquina), depois de enviar:
#   /opt/autoitil/app.tar        backend/, frontend/, db/ e infra/ (git archive)
#   /dev/shm/autoitil-input      CHAVE=VALOR por linha: DATABASE_URL, S3_BUCKET,
#                                AWS_DEFAULT_REGION, HF_TOKEN e, opcionais,
#                                ADMIN_EMAIL e ADMIN_PASSWORD. Fica em RAM e e
#                                apagado depois de lido.
#
# Modos:
#   start   dispara o deploy em segundo plano; ele sobrevive a queda do SSH
#           (o primeiro build leva de 15 a 30 min)
#   follow  acompanha o deploy.log ate o fim e sai com o codigo do deploy
#   run     o deploy em si (uso interno do start)
#
# Pode rodar de novo a cada deploy: o schema so e aplicado em banco vazio, o
# JWT_SECRET_KEY e preservado e o administrador so e criado se nao existir.
# As mensagens nao tem acento porque aparecem no terminal do Windows.
set -euo pipefail

BASE=/opt/autoitil
LOG=$BASE/deploy.log
INPUT=/dev/shm/autoitil-input
cd "$BASE"

log() { printf '[%s] %s\n' "$(date +%T)" "$*"; }
die() { log "ERRO: $*" >&2; exit 1; }

case "${1:-}" in
  start)
    if pgrep -f "remote-deploy.sh run" >/dev/null; then die "ja existe um deploy em andamento"; fi
    [[ -s app.tar && -s $INPUT ]] || die "app.tar ou $INPUT nao chegaram"
    chmod 600 "$INPUT"
    : > "$LOG"
    chmod 600 "$LOG" # pode conter a senha gerada para o administrador
    nohup setsid bash "$BASE/remote-deploy.sh" run > "$LOG" 2>&1 < /dev/null &
    exit 0
    ;;
  follow)
    [[ -f $LOG ]] || die "nenhum deploy encontrado em $LOG"
    tail -n "${2:-+1}" -F "$LOG" & # +1 = do comeco; N = so as ultimas N linhas
    tail_pid=$!
    until grep -q '^##DONE' "$LOG"; do sleep 2; done
    sleep 1
    kill "$tail_pid" 2>/dev/null || true
    exit "$(grep -o '^##DONE:[0-9]*' "$LOG" | tail -1 | cut -d: -f2)"
    ;;
  run) ;;
  *) die "uso: remote-deploy.sh start | follow [linhas] | run" ;;
esac

trap 'echo "##DONE:$?"' EXIT # e o que o "follow" espera para sair

# ------------------------------------------------------------------ entrada ---
declare -A IN
while IFS= read -r line || [[ -n $line ]]; do
  line="${line#$'\xef\xbb\xbf'}" # tolera BOM e CRLF vindos do Windows
  line="${line%$'\r'}"
  if [[ $line == *=* ]]; then IN[${line%%=*}]="${line#*=}"; fi
done < "$INPUT"
rm -f "$INPUT"
for k in DATABASE_URL S3_BUCKET AWS_DEFAULT_REGION HF_TOKEN; do
  [[ -n ${IN[$k]:-} ]] || die "a variavel $k nao chegou"
done

# ------------------------------------------------------------------- codigo ---
log "Extraindo o codigo..."
rm -rf app
mkdir app
tar -xf app.tar -C app
rm app.tar

# --------------------------------------------------------------------- .env ---
# Lido pelo compose. O JWT_SECRET_KEY e gerado no primeiro deploy e mantido.
JWT=$(grep -s '^JWT_SECRET_KEY=' .env | cut -d= -f2- || true)
umask 077
cat > .env <<EOF
DATABASE_URL=${IN[DATABASE_URL]}
S3_BUCKET=${IN[S3_BUCKET]}
AWS_DEFAULT_REGION=${IN[AWS_DEFAULT_REGION]}
JWT_SECRET_KEY=${JWT:-$(openssl rand -hex 32)}
EOF
umask 022

# -------------------------------------------------------------------- banco ---
PGURL="${IN[DATABASE_URL]/+psycopg/}" # o psql nao conhece o sufixo do driver
log "Aguardando o RDS aceitar conexoes..."
for _ in $(seq 60); do
  pg_isready -q -d "$PGURL" && break
  sleep 5
done
vazio=$(psql "$PGURL" -tAc "SELECT to_regclass('autoitil.usuario') IS NULL")
if [[ $vazio == t ]]; then
  log "Banco vazio: aplicando db/schema.sql..."
  # --single-transaction: se falhar no meio, nao sobra schema pela metade.
  psql "$PGURL" -q -v ON_ERROR_STOP=1 --single-transaction -f app/db/schema.sql
else
  log "O schema ja existe no banco: nada a aplicar."
fi

# -------------------------------------------------------------- conteineres ---
# sudo evita depender de o grupo docker ja valer nesta sessao.
DC=(sudo -E docker compose -f app/infra/docker-compose.aws.yml --env-file .env)
log "Build e subida dos conteineres (a primeira vez leva de 15 a 30 min)..."
# --wait so retorna com o backend saudavel (modelos carregados) e o nginx no ar.
if ! HF_TOKEN="${IN[HF_TOKEN]}" "${DC[@]}" up -d --build --wait; then
  "${DC[@]}" logs --tail 60 backend || true
  die "os conteineres nao subiram. Disco cheio? Rode: sudo docker system prune -af"
fi
sudo docker image prune -f > /dev/null
curl -fsS -o /dev/null --retry 10 --retry-delay 3 --retry-all-errors http://127.0.0.1/api/health \
  || die "o nginx nao alcancou o backend em /api/health"
log "Aplicacao no ar."

# ---------------------------------------------------------------- bucket S3 ---
# Cria o bucket de uploads se nao existir (ver main.tf: nao e do Terraform).
# Roda no conteiner do backend, que ja tem o boto3 e usa o instance profile.
"${DC[@]}" exec -T backend python - <<'PY' || die "sem acesso ao bucket S3. O instance profile esta anexado a EC2?"
import os

import boto3
from botocore.exceptions import ClientError

bucket, region = os.environ["S3_BUCKET"], os.environ["AWS_DEFAULT_REGION"]
s3 = boto3.client("s3", region_name=region)
try:
    s3.head_bucket(Bucket=bucket)
except ClientError as err:
    if err.response["Error"]["Code"] not in ("404", "NoSuchBucket", "NotFound"):
        raise  # 403 = o nome pertence a outra conta, ou falta permissao
    # us-east-1 nao aceita LocationConstraint
    extra = {} if region == "us-east-1" else {"CreateBucketConfiguration": {"LocationConstraint": region}}
    s3.create_bucket(Bucket=bucket, **extra)
PY
log "Bucket de uploads: ${IN[S3_BUCKET]}"

# ------------------------------------------------------------ administrador ---
# O schema nao semeia usuario. Sem ADMIN_PASSWORD, o administrador so e criado
# (com senha aleatoria) se ainda nao houver nenhum; com ADMIN_PASSWORD, ele e
# criado ou tem a senha redefinida (backend/scripts/create_admin.py).
export ADMIN_EMAIL="${IN[ADMIN_EMAIL]:-}" ADMIN_PASSWORD="${IN[ADMIN_PASSWORD]:-}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@autoitil.local}"
admins=$(psql "$PGURL" -tAc "SELECT count(*) FROM autoitil.usuario WHERE is_admin")
if [[ -z $ADMIN_PASSWORD && $admins == 0 ]]; then
  ADMIN_PASSWORD=$(openssl rand -hex 12)
  log "Login: $ADMIN_EMAIL   Senha: $ADMIN_PASSWORD   <-- anote agora, ela nao aparece de novo"
fi
if [[ -n $ADMIN_PASSWORD ]]; then
  # -e NOME (sem valor) herda do ambiente: a senha nao aparece no ps.
  "${DC[@]}" exec -T -e ADMIN_EMAIL -e ADMIN_PASSWORD backend python -m scripts.create_admin
else
  log "Administrador ja existe: senha mantida."
fi

log "Deploy concluido."
