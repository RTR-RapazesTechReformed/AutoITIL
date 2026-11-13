# Infraestrutura AWS

Terraform e scripts que colocam o AutoITIL no ar em uma conta AWS. Foi pensado para o AWS Academy Learner Lab e atende a demonstração, não um ambiente de produção.

| Recurso | Descrição |
|---|---|
| EC2 `t3.large` + Elastic IP | Ubuntu 24.04 com Docker; roda `backend` (FastAPI) e `frontend` (nginx) |
| RDS PostgreSQL 16 | `db.t3.micro`, 20 GB, criptografado; o app conecta com `sslmode=require` |
| Bucket S3 | Uploads. É criado pelo deploy, não pelo Terraform (ver [Problemas comuns](#problemas-comuns)) |
| 2 security groups | App (SSH e HTTP 80) e banco (5432) |

Só a porta 80 é publicada. O nginx faz proxy de `/api` para o backend, o banco aceita a EC2 pelo security group e o backend acessa o S3 pelo instance profile, sem chave no contêiner.

## Subir na AWS

Os comandos abaixo são para o PowerShell, rodados na raiz do repositório. No Linux, macOS ou Git Bash, troque o passo 6 por `bash infra/deploy.sh ~/Downloads/labsuser.pem`.

### Uma vez por máquina

Instale o Terraform (Git e OpenSSH já vêm no Windows 10 e 11) e abra um terminal novo:

```powershell
winget install Hashicorp.Terraform
```

Tenha também um token do Hugging Face cuja conta aceitou a licença do [`google/gemma-3-1b-it`](https://huggingface.co/google/gemma-3-1b-it). Sem ela, o build falha ao baixar o modelo.

### A cada subida

**1. Inicie o lab.** No Learner Lab, clique em `Start Lab` e espere a bolinha ficar verde.

**2. Credenciais.** Em `AWS Details` → `AWS CLI` → `Show`, copie o bloco inteiro (começa com `[default]`) e salve no arquivo de credenciais. Elas vencem em cerca de 4 horas; quando o Terraform reclamar de `ExpiredToken`, repita este passo.

```powershell
New-Item -ItemType Directory -Force $HOME\.aws | Out-Null
Get-Clipboard | Set-Content -Encoding ascii $HOME\.aws\credentials
```

Na mesma tela, clique em `Download PEM` para baixar a chave SSH (`labsuser.pem`).

**3. Variáveis.** Só na primeira vez: copie o modelo e preencha `db_password` e `allowed_cidr` com seu IP público e `/32` (veja em https://checkip.amazonaws.com). Esse IP só controla o SSH que o deploy usa: o site fica aberto para qualquer pessoa. Se você mudou de rede, atualize o IP antes do deploy.

O `terraform.tfvars` guarda a senha do banco e **não vai para o git** (está no `.gitignore`). Cada pessoa que for subir a infra cria o seu.

```powershell
Copy-Item infra\terraform.tfvars.example infra\terraform.tfvars
notepad infra\terraform.tfvars
```

**4. Infraestrutura.** O `apply` mostra o que vai criar e pede `yes`. Leva de 8 a 10 minutos, quase tudo do RDS.

```powershell
terraform -chdir=infra init
terraform -chdir=infra apply
```

**5. Commit.** O deploy envia só o que está **commitado** no `HEAD`; arquivos novos ou alterados fora do commit não sobem. Nenhum segredo entra no commit: `.env`, `terraform.tfvars`, `*.tfstate` e `*.pem` são ignorados pelo git. Mesmo assim, confira a lista do `git status` antes de commitar.

```powershell
git status
git add infra README.md .gitignore
git commit -m "sua mensagem"
```

Os segredos que a aplicação usa nunca passam pelo git: a senha do banco sai do Terraform, o `HF_TOKEN` e a senha do admin vêm do seu terminal, e o `JWT_SECRET_KEY` é gerado na própria EC2.

**6. Aplicação.** Faz o build na EC2 e sobe os contêineres. O primeiro build leva de 15 a 30 minutos, porque baixa cerca de 1,8 GB de modelos.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # libera scripts só nesta janela
$env:HF_TOKEN = "hf_..."                                     # ou deixe que o script pergunte
.\infra\deploy.ps1 $HOME\Downloads\labsuser.pem
```

No fim aparece o endereço do site (`http://<ip>`). No primeiro deploy, o administrador `admin@autoitil.local` é criado com uma senha aleatória, **mostrada uma única vez** no log: anote. Para escolher o e-mail e a senha, ou redefinir a senha depois, defina antes do deploy:

```powershell
$env:ADMIN_EMAIL = "voce@exemplo.com"
$env:ADMIN_PASSWORD = "uma-senha-com-12-ou-mais"
```

### Quando o lab é reiniciado

Ao encerrar a sessão, o Learner Lab desliga a EC2 e o RDS, mas não os apaga. No próximo `Start Lab` eles voltam sozinhos e os contêineres sobem de novo em alguns minutos, no mesmo IP. Basta refazer o passo 2 se for rodar o Terraform ou o deploy.

## Dia a dia

| Para | Faça |
|---|---|
| Publicar código novo | Commit e rode o `deploy` de novo. O cache do Docker é reaproveitado |
| Restringir o site a alguns IPs | `http_allowed_cidrs = ["IP/32", ...]` no `terraform.tfvars` e `terraform apply` (o padrão é aberto) |
| Atualizar seu IP do SSH, quando ele mudar | Ajuste `allowed_cidr` (e `db_allowed_cidrs`) e `terraform apply` |
| Acessar o banco da sua máquina | Ponha seu IP em `db_allowed_cidrs`, `terraform apply` e conecte em `terraform output db_host` (banco e usuário `autoitil`) |
| Recriar a EC2 preservando o banco | `terraform apply "-replace=aws_instance.app"` e rode o `deploy` |
| Apagar tudo | `terraform destroy`. O bucket S3 fica: apague pelo console |

Se a janela fechar no meio do build, o deploy continua na EC2. Para voltar a acompanhar ou ver os logs:

```bash
ssh -i infra/.deploy/key.pem ubuntu@<ip> 'bash /opt/autoitil/remote-deploy.sh follow'
ssh -i infra/.deploy/key.pem ubuntu@<ip> 'sudo docker logs -f autoitil-backend-1'
```

O `db/schema.sql` só é aplicado em banco vazio. Para recomeçar do zero, rode `DROP SCHEMA autoitil CASCADE;` no banco e faça o deploy de novo.

## Arquivos

| Arquivo | Função |
|---|---|
| `main.tf`, `variables.tf`, `outputs.tf` | Terraform |
| `user_data.sh` | Prepara a EC2 no primeiro boot: Docker, `psql` e 4 GB de swap. Qualquer mudança nele recria a instância |
| `deploy.ps1`, `deploy.sh` | Rodam na sua máquina: empacotam o `HEAD`, enviam por `scp` e acompanham o log |
| `remote-deploy.sh` | Roda na EC2: grava o `.env`, aplica o schema, faz o build, cria o bucket e o administrador |
| `docker-compose.aws.yml` | Compose da EC2: backend e frontend, sem Postgres nem MinIO |

## Segurança

- **Site aberto e HTTP puro.** Qualquer pessoa alcança a tela de login, e não há TLS: e-mail, senha e JWT trafegam em claro. O acesso aos dados depende só das senhas, então use uma senha forte para o admin e não reaproveite senhas pessoais. Se quiser fechar o site depois da apresentação, use `http_allowed_cidrs` ou `terraform destroy`.
- **SSH e banco** continuam restritos: o SSH só aceita `allowed_cidr`, e o banco só aceita a EC2 (mais `db_allowed_cidrs`, se você preencher).
- **Segredos fora do git.** `.env`, `terraform.tfvars`, `*.tfstate` (guarda a senha do banco em texto claro), `.deploy/` e `*.pem` estão no `.gitignore`. Confira o `git status` antes de cada commit.
- **Na EC2.** O `JWT_SECRET_KEY` é gerado no primeiro deploy e fica em `/opt/autoitil/.env` (modo 600). O `HF_TOKEN` só é usado no build, mas pode aparecer no `docker history` da imagem: use um token somente leitura.

## Problemas comuns

| Sintoma | Causa e solução |
|---|---|
| `ExpiredToken` ou `InvalidClientTokenId` | As credenciais do lab venceram: cole o bloco novo em `~/.aws/credentials` |
| `Connection timed out` no SSH ou no site | Seu IP mudou: atualize `allowed_cidr` e rode `terraform apply` |
| `REMOTE HOST IDENTIFICATION HAS CHANGED` | A instância foi recriada: apague `infra/.deploy/known_hosts` |
| Build falha em `bake_models` com 401 ou 403 | O `HF_TOKEN` não tem a licença do `google/gemma-3-1b-it` aceita |
| `no space left on device` | `sudo docker system prune -af` na EC2 e rode o `deploy` de novo |
| `sem acesso ao bucket S3` no fim do deploy | O instance profile (`LabInstanceProfile`) não existe na conta ou não está anexado à EC2 |
| `AccessDenied ... service control policy` ao criar bucket pelo Terraform | O Learner Lab bloqueia leituras de S3 que o provider faz. Por isso o bucket é criado pelo deploy |
| Script bloqueado no PowerShell | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
