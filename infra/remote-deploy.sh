#!/usr/bin/env bash
# Roda NA EC2, como o usuário ubuntu. Quem chama é o infra/deploy.* (da sua
# máquina), depois de enviar:
#   /opt/autoitil/app.tar        backend/, frontend/, db/ e infra/ (git archive)
#   /dev/shm/autoitil-input      CHAVE=VALOR por linha: DATABASE_URL, S3_BUCKET,
#                                AWS_DEFAULT_REGION, HF_TOKEN e, opcionais,
#                                ADMIN_EMAIL e ADMIN_PASSWORD. Fica em RAM e é
#                                apagado depois de lido.
#
# Modos:
#   start   dispara o deploy em segundo plano; ele sobrevive à queda do SSH
#           (o primeiro build leva de 15 a 30 min)
#   follow  acompanha o deploy.log até o fim e sai com o código do deploy
#   run     o deploy em si (uso interno do start)
#
# Pode rodar de novo a cada deploy: o schema só é aplicado em banco vazio, o
# JWT_SECRET_KEY é preservado e o administrador só é criado se não existir.
set -euo pipefail

BASE=/opt/autoitil
LOG=$BASE/deploy.log
INPUT=/dev/shm/autoitil-input
cd "$BASE"

log() { printf '[%s] %s\n' "$(date +%T)" "$*"; }
die() { log "ERRO: $*" >&2; exit 1; }

case "${1:-}" in
  start)
    if pgrep -f "remote-deploy.sh run" >/dev/null; then die "já existe um deploy em andamento"; fi
    [[ -s app.tar && -s $INPUT ]] || die "app.tar ou $INPUT não chegaram"
    chmod 600 "$INPUT"
    : > "$LOG"
    chmod 600 "$LOG" # pode conter a senha gerada para o administrador
    nohup setsid bash "$BASE/remote-deploy.sh" run > "$LOG" 2>&1 < /dev/null &
    exit 0
    ;;
  follow)
    [[ -f $LOG ]] || die "nenhum deploy encontrado em $LOG"
    tail -n "${2:-+1}" -F "$LOG" & # +1 = do começo; N = só as últimas N linhas
    tail_pid=$!
    until grep -q '^##DONE' "$LOG"; do sleep 2; done
    sleep 1
    kill "$tail_pid" 2>/dev/null || true
    exit "$(grep -o '^##DONE:[0-9]*' "$LOG" | tail -1 | cut -d: -f2)"
    ;;
  run) ;;
  *) die "uso: remote-deploy.sh start | follow [linhas] | run" ;;
esac

trap 'echo "##DONE:$?"' EXIT # é o que o "follow" espera para sair

# ------------------------------------------------------------------ entrada ---
declare -A IN
while IFS= read -r line || [[ -n $line ]]; do
  line="${line#$'\xef\xbb\xbf'}" # tolera BOM e CRLF vindos do Windows
  line="${line%$'\r'}"
  if [[ $line == *=* ]]; then IN[${line%%=*}]="${line#*=}"; fi
done < "$INPUT"
rm -f "$INPUT"
for k in DATABASE_URL S3_BUCKET AWS_DEFAULT_REGION HF_TOKEN; do
  [[ -n ${IN[$k]:-} ]] || die "a variável $k não chegou"
done

# ------------------------------------------------------------------- código ---
log "Extraindo o código..."
rm -rf app
mkdir app
tar -xf app.tar -C app
rm app.tar

# --------------------------------------------------------------------- .env ---
# Lido pelo compose. O JWT_SECRET_KEY é gerado no primeiro deploy e mantido.
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
PGURL="${IN[DATABASE_URL]/+psycopg/}" # o psql não conhece o sufixo do driver
log "Aguardando o RDS aceitar conexões..."
for _ in $(seq 60); do
  pg_isready -q -d "$PGURL" && break
  sleep 5
done
vazio=$(psql "$PGURL" -tAc "SELECT to_regclass('autoitil.usuario') IS NULL")
if [[ $vazio == t ]]; then
  log "Banco vazio: aplicando db/schema.sql..."
  # --single-transaction: se falhar no meio, não sobra schema pela metade.
  psql "$PGURL" -q -v ON_ERROR_STOP=1 --single-transaction -f app/db/schema.sql
else
  log "O schema já existe no banco: nada a aplicar."
fi

# -------------------------------------------------------------- contêineres ---
# sudo evita depender de o grupo docker já valer nesta sessão.
DC=(sudo -E docker compose -f app/infra/docker-compose.aws.yml --env-file .env)
log "Build e subida dos contêineres (a primeira vez leva de 15 a 30 min)..."
# --wait só retorna com o backend saudável (modelos carregados) e o nginx no ar.
if ! HF_TOKEN="${IN[HF_TOKEN]}" "${DC[@]}" up -d --build --wait; then
  "${DC[@]}" logs --tail 60 backend || true
  die "os contêineres não subiram. Disco cheio? Rode: sudo docker system prune -af"
fi
sudo docker image prune -f > /dev/null
curl -fsS -o /dev/null --retry 10 --retry-delay 3 --retry-all-errors http://127.0.0.1/api/health \
  || die "o nginx não alcançou o backend em /api/health"
log "Aplicação no ar."

# ---------------------------------------------------------------- bucket S3 ---
# Cria o bucket de uploads se não existir (ver main.tf: não é do Terraform).
# Roda no contêiner do backend, que já tem o boto3 e usa o instance profile.
"${DC[@]}" exec -T backend python - <<'PY' || die "sem acesso ao bucket S3. O instance profile está anexado à EC2?"
import os

import boto3
from botocore.exceptions import ClientError

bucket, region = os.environ["S3_BUCKET"], os.environ["AWS_DEFAULT_REGION"]
s3 = boto3.client("s3", region_name=region)
try:
    s3.head_bucket(Bucket=bucket)
except ClientError as err:
    if err.response["Error"]["Code"] not in ("404", "NoSuchBucket", "NotFound"):
        raise  # 403 = o nome pertence a outra conta, ou falta permissão
    # us-east-1 não aceita LocationConstraint
    extra = {} if region == "us-east-1" else {"CreateBucketConfiguration": {"LocationConstraint": region}}
    s3.create_bucket(Bucket=bucket, **extra)
PY
log "Bucket de uploads: ${IN[S3_BUCKET]}"

# ------------------------------------------------------------ administrador ---
# O schema não semeia usuário. Sem ADMIN_PASSWORD, o administrador só é criado
# (com senha aleatória) se ainda não houver nenhum; com ADMIN_PASSWORD, ele é
# criado ou tem a senha redefinida (backend/scripts/create_admin.py).
export ADMIN_EMAIL="${IN[ADMIN_EMAIL]:-}" ADMIN_PASSWORD="${IN[ADMIN_PASSWORD]:-}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@autoitil.local}"
admins=$(psql "$PGURL" -tAc "SELECT count(*) FROM autoitil.usuario WHERE is_admin")
if [[ -z $ADMIN_PASSWORD && $admins == 0 ]]; then
  ADMIN_PASSWORD=$(openssl rand -hex 12)
  log "Administrador criado. Login: $ADMIN_EMAIL | Senha: $ADMIN_PASSWORD (anote agora: ela não será exibida novamente)"
fi
if [[ -n $ADMIN_PASSWORD ]]; then
  # -e NOME (sem valor) herda do ambiente: a senha não aparece no ps.
  "${DC[@]}" exec -T -e ADMIN_EMAIL -e ADMIN_PASSWORD backend python -m scripts.create_admin
else
  log "Administrador já existe: senha mantida."
fi

log "Deploy concluído."
