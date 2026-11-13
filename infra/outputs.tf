output "app_url" {
  description = "Endereço do site (tela de login). A API fica em /api, atrás do nginx."
  value       = "http://${aws_eip.app.public_ip}"
}

output "public_ip" {
  description = "IP fixo da EC2 (SSH com o usuário ubuntu)."
  value       = aws_eip.app.public_ip
}

output "db_host" {
  description = "Endereço do RDS. Banco e usuário: autoitil; senha: DB_PASSWORD do infra/.env. Fora da AWS, só responde ao seu IP."
  value       = aws_db_instance.postgres.address
}

output "deploy_env" {
  description = "Variáveis que o deploy envia à EC2. A senha já vai codificada para caber na URL."
  sensitive   = true
  value       = <<-EOT
    DATABASE_URL=postgresql+psycopg://${local.name}:${replace(urlencode(local.db_password), "+", "%20")}@${aws_db_instance.postgres.address}:5432/${local.name}?sslmode=require
    S3_BUCKET=${local.uploads_bucket}
    AWS_DEFAULT_REGION=${var.region}
  EOT
}
