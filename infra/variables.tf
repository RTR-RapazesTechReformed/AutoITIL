# Todas opcionais. Os segredos (credenciais AWS, senha do banco) ficam no
# infra/.env. Para mudar algum valor abaixo, crie infra/terraform.tfvars com
# NOME = valor (o arquivo não vai para o git).

variable "http_allowed_cidrs" {
  description = <<-EOT
    CIDRs liberados para o site (HTTP 80). O padrão abre para qualquer pessoa.
    O tráfego é HTTP puro e não há limite de requisições.
  EOT
  type        = list(string)
  default     = ["0.0.0.0/0"]

  validation {
    condition     = alltrue([for c in var.http_allowed_cidrs : can(cidrhost(c, 0))])
    error_message = "Cada entrada precisa ser um CIDR com o tamanho do prefixo, como \"0.0.0.0/0\"."
  }
}

variable "allowed_cidr" {
  description = "CIDR liberado para SSH e para o banco. Vazio = o seu IP público, detectado a cada apply."
  type        = string
  default     = null

  validation {
    condition     = var.allowed_cidr == null || can(cidrhost(var.allowed_cidr, 0))
    error_message = "Informe um CIDR com o tamanho do prefixo: \"203.0.113.10/32\", não \"203.0.113.10\"."
  }
}

variable "ssh_key_name" {
  description = "Key pair EC2 já existente na conta. No Learner Lab é \"vockey\" (labsuser.pem)."
  type        = string
  default     = "vockey"
}

variable "instance_profile" {
  description = "Instance profile da EC2, que dá ao backend acesso ao S3. O Learner Lab não deixa criar roles; use o que já existe."
  type        = string
  default     = "LabInstanceProfile"
}

variable "instance_type" {
  description = "Tipo da EC2. O backend carrega dois modelos BERT e o Gemma 3 1B na CPU: com menos de 8 GB o enriquecimento é morto por falta de memória."
  type        = string
  default     = "t3.large"
}

variable "region" {
  description = "Região AWS. O Learner Lab só libera us-east-1 e us-west-2."
  type        = string
  default     = "us-east-1"
}
