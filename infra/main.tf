# =============================================================================
# AutoITIL — infraestrutura AWS: uma EC2 com Docker, um RDS PostgreSQL e um
# bucket S3, na VPC padrão da conta. Pensada para o AWS Academy Learner Lab.
# =============================================================================
terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.4"
    }
  }
}

# Credenciais: as do infra/.env. Sem elas, a cadeia padrão do provider
# (~/.aws/credentials ou variáveis AWS_*).
provider "aws" {
  region     = var.region
  access_key = try(local.env["AWS_ACCESS_KEY_ID"], null)
  secret_key = try(local.env["AWS_SECRET_ACCESS_KEY"], null)
  token      = try(local.env["AWS_SESSION_TOKEN"], null)

  default_tags {
    tags = {
      Project   = local.name
      Terraform = "true"
    }
  }
}

locals {
  name = "autoitil" # prefixo dos recursos, nome do banco e do usuário master

  # infra/.env: uma linha CHAVE=VALOR por variável. Aceita o bloco do Learner
  # Lab colado como vem (linha [default] e chaves em minúsculas). Se uma chave
  # aparecer duas vezes, vale a última; valores vazios são ignorados.
  env_lines = regexall(
    "(?m)^[ \\t]*([A-Za-z_][A-Za-z0-9_]*)[ \\t]*=[ \\t]*(.*?)[ \\t\\r]*$",
    fileexists("${path.module}/.env") ? file("${path.module}/.env") : ""
  )
  env_all = { for m in local.env_lines : upper(m[0]) => trim(m[1], "\"'")... }
  env = sensitive({
    for k, vs in local.env_all : k => vs[length(vs) - 1] if vs[length(vs) - 1] != ""
  })

  db_password = try(local.env["DB_PASSWORD"], "")

  # Seu IP público, detectado a cada plan/apply: só ele acessa o SSH e o banco.
  my_ip   = trimspace(data.http.my_ip.response_body)
  my_cidr = coalesce(var.allowed_cidr, "${local.my_ip}/32")

  # O bucket NÃO é um recurso do Terraform: no Learner Lab uma política da
  # organização (SCP) nega as leituras de S3 que o provider faz logo após criar
  # o bucket, e o apply falha com AccessDenied. Quem cria é o remote-deploy.sh,
  # com o instance profile da EC2. Aqui só se calcula o nome.
  uploads_bucket = "${local.name}-uploads-${data.aws_caller_identity.current.account_id}"
}

data "aws_caller_identity" "current" {}

data "http" "my_ip" {
  url = "https://checkip.amazonaws.com"
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

# -----------------------------------------------------------------------------
# Security groups
# -----------------------------------------------------------------------------
resource "aws_security_group" "app" {
  name        = "${local.name}-app"
  description = "Acesso a aplicacao e SSH" # a AWS só aceita ASCII aqui
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [local.my_cidr]
  }

  # Só o frontend (nginx) é publicado. A API não fica exposta: o nginx faz
  # proxy de /api para o contêiner do backend dentro da rede do compose.
  ingress {
    description = "HTTP - frontend"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.http_allowed_cidrs
  }

  egress {
    description = "Saida liberada: pip, Docker Hub, Hugging Face"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "database" {
  name        = "${local.name}-db"
  description = "PostgreSQL access"
  vpc_id      = data.aws_vpc.default.id

  # A EC2 alcança o banco pela identidade (security group), não por faixa de IP.
  ingress {
    description     = "PostgreSQL from the application instance"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  # Acesso direto da sua máquina (DBeaver, pgAdmin, psql).
  ingress {
    description = "PostgreSQL from developer machines"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [local.my_cidr]
  }
}

# -----------------------------------------------------------------------------
# Banco de dados
# -----------------------------------------------------------------------------
resource "aws_db_subnet_group" "default" {
  name       = "${local.name}-subnets"
  subnet_ids = data.aws_subnets.default.ids
}

resource "aws_db_instance" "postgres" {
  identifier     = "${local.name}-db"
  engine         = "postgres"
  engine_version = "16"
  instance_class = "db.t3.micro" # a classe que o Learner Lab libera

  allocated_storage     = 20
  max_allocated_storage = 0 # sem autoescala
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = local.name
  username = local.name
  password = local.db_password
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.default.name
  vpc_security_group_ids = [aws_security_group.database.id]

  # Endereço público para a sua máquina alcançar o banco; o security group só
  # libera a EC2 e o seu IP.
  publicly_accessible = true

  # Ambiente de demonstração: sem backup, monitoramento ou snapshot final.
  monitoring_interval          = 0
  performance_insights_enabled = false
  backup_retention_period      = 0
  skip_final_snapshot          = true
  deletion_protection          = false
  apply_immediately            = true

  lifecycle {
    precondition {
      # Regras do RDS: 8 a 128 caracteres, sem / @ " nem espaço.
      condition     = can(regex("^[^/@\" ]{8,128}$", nonsensitive(local.db_password)))
      error_message = "Defina DB_PASSWORD no infra/.env: 8 ou mais caracteres, sem / @ \" nem espaço."
    }
  }
}

# -----------------------------------------------------------------------------
# Aplicação
# -----------------------------------------------------------------------------
resource "aws_instance" "app" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = var.ssh_key_name
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = var.instance_profile

  # Hop limit 2: o backend roda em contêiner (uma rede a mais) e lê as
  # credenciais do instance profile pelo IMDS. Com o padrão (1), o S3 falha
  # com NoCredentialsError mesmo com o profile anexado.
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  # A imagem do backend tem ~7,4 GB (PyTorch e os modelos) e o build deixa
  # camadas intermediárias; 40 GB dão folga para alguns redeploys.
  root_block_device {
    volume_size = 40
    volume_type = "gp3"
  }

  # Só prepara a máquina (Docker, psql, swap). O código chega pelo deploy.
  # Atenção: qualquer mudança no user_data.sh recria a instância.
  user_data                   = file("${path.module}/user_data.sh")
  user_data_replace_on_change = true

  tags = {
    Name = "${local.name}-app"
  }
}

resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"
}
