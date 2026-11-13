# Infraestrutura AWS

Coloca o AutoITIL no ar no AWS Academy Learner Lab: uma EC2 com Docker (backend e frontend), um RDS PostgreSQL e um bucket S3 para os uploads. O site fica aberto para qualquer pessoa; o SSH e o banco só aceitam o IP de quem rodou o Terraform.

## Antes de começar

- Acesso a um **AWS Academy Learner Lab**.
- Um **token do Hugging Face** (https://huggingface.co/settings/tokens) de uma conta que aceitou a licença do [`google/gemma-3-1b-it`](https://huggingface.co/google/gemma-3-1b-it). Sem a licença, o build falha.
- **Git e Terraform**. Depois de instalar, feche e abra o terminal:

```powershell
winget install Git.Git
winget install Hashicorp.Terraform
git clone https://github.com/RTR-RapazesTechReformed/AutoITIL.git
cd AutoITIL
```

## Subir

Todos os comandos rodam no PowerShell, na pasta raiz do repositório.

**1. Preencha o `infra/.env`.** Ele guarda toda a configuração e não vai para o git.

```powershell
Copy-Item infra\.env.example infra\.env
notepad infra\.env
```

| Campo | O que colocar |
|---|---|
| Bloco `aws_...` | Learner Lab: `Start Lab` → `AWS Details` → `AWS CLI` → `Show`. Copie o bloco inteiro e cole por cima |
| `DB_PASSWORD` | Uma senha inventada para o banco: 8 ou mais caracteres, sem `/`, `@`, `"` nem espaço |
| `HF_TOKEN` | O token do Hugging Face |
| `SSH_KEY` | Caminho do `labsuser.pem` (`AWS Details` → `Download PEM`). Vazio = pasta Downloads |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Seu login no site (senha com 12 ou mais caracteres) |

**2. Crie a infraestrutura.** Digite `yes` quando pedir. Leva de 8 a 10 minutos.

```powershell
terraform -chdir=infra init
terraform -chdir=infra apply
```

**3. Suba a aplicação.** A primeira vez leva de 15 a 30 minutos, porque baixa os modelos.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\infra\deploy.ps1
```

O Windows bloqueia scripts `.ps1` por padrão. A primeira linha libera a execução **só nesta janela do terminal**: ao fechá-la, o bloqueio volta, sem mudar nada no sistema. No Linux, macOS ou Git Bash, rode só `bash infra/deploy.sh`.

No fim aparece o endereço do site (`http://<ip>`). Entre com o `ADMIN_EMAIL` e o `ADMIN_PASSWORD`; pelo site, o administrador cria as contas das outras pessoas. Se deixou a senha vazia, o deploy cria `admin@autoitil.local` com uma senha aleatória, mostrada **uma única vez** no fim do log.

## Dia a dia

| Para | Faça |
|---|---|
| Publicar código novo | Faça commit e rode `.\infra\deploy.ps1`. Só o que está commitado é enviado |
| Credenciais vencidas (`ExpiredToken`) | Duram cerca de 4 horas: cole o bloco novo do Learner Lab no `.env` |
| SSH ou deploy não conecta | Seu IP mudou: rode `terraform -chdir=infra apply` de novo |
| Apagar tudo | `terraform -chdir=infra destroy`. O bucket S3 fica: apague pelo console |

Ao encerrar a sessão, o Learner Lab desliga a EC2 e o RDS sem apagá-los. No próximo `Start Lab`, o site volta sozinho em alguns minutos, no mesmo IP.

O Terraform guarda o que criou em `infra/terraform.tfstate`, só na máquina de quem rodou o `apply`. Só essa máquina consegue fazer o deploy ou apagar essa infra; outra pessoa que seguir este guia cria uma infra separada.

## Problemas comuns

| Sintoma | Solução |
|---|---|
| `Defina DB_PASSWORD no infra/.env` | Senha vazia, curta ou com `/`, `@`, `"` ou espaço |
| Build falha em `bake_models` com 401 ou 403 | Aceite a licença do `google/gemma-3-1b-it` na conta do `HF_TOKEN` |
| `REMOTE HOST IDENTIFICATION HAS CHANGED` | A EC2 foi recriada: apague `infra/.deploy/known_hosts` |
| `no space left on device` | Na EC2: `sudo docker system prune -af`, e rode o deploy de novo |
| A janela fechou no meio do deploy | Ele continua na EC2. Acompanhe com `ssh -i infra/.deploy/key.pem ubuntu@<ip> 'bash /opt/autoitil/remote-deploy.sh follow'` |

## Segurança

O site usa HTTP sem TLS: senhas trafegam em claro. Use uma senha de admin exclusiva e rode `terraform destroy. O `.env`, o `terraform.tfstate` (que guarda a senha do banco) e a chave `.pem` estão no `.gitignore`.