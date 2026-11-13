<#
.SYNOPSIS
  Publica na EC2 o que está COMMITADO (HEAD) neste repositório.
.DESCRIPTION
  Rode na sua máquina, depois do "terraform apply", e de novo a cada mudança de
  código. É o equivalente do infra/deploy.sh para o PowerShell.

  Lê do infra\.env: HF_TOKEN, SSH_KEY (padrão: Downloads\labsuser.pem),
  ADMIN_EMAIL e ADMIN_PASSWORD. Uma variável de ambiente com o mesmo nome tem
  prioridade sobre o arquivo.
.EXAMPLE
  .\infra\deploy.ps1
#>

# ssh, git e terraform escrevem avisos em stderr; com 'Stop' o PowerShell 5.1
# trataria isso como erro. Os códigos de saída são checados à mão.
$ErrorActionPreference = 'Continue'
# Exibe corretamente os acentos do log que vem da EC2 (UTF-8).
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$Infra  = $PSScriptRoot
$Deploy = Join-Path $Infra '.deploy'
function Fail([string]$Message) { Write-Host "ERRO: $Message" -ForegroundColor Red; exit 1 }

# Valor de uma chave: ambiente primeiro, depois infra\.env (a última ocorrência).
$EnvFile = Join-Path $Infra '.env'
function Cfg([string]$Name) {
    $v = [Environment]::GetEnvironmentVariable($Name)
    if (-not $v -and (Test-Path $EnvFile)) {
        $line = Get-Content $EnvFile | Where-Object { $_ -match "^\s*$Name\s*=" } | Select-Object -Last 1
        if ($line) { $v = ($line -replace "^\s*$Name\s*=", '').Trim().Trim('"').Trim("'") }
    }
    return $v
}

$KeyFile = Cfg 'SSH_KEY'
if (-not $KeyFile) { $KeyFile = Join-Path $HOME 'Downloads\labsuser.pem' }
if (-not (Test-Path $KeyFile)) { Fail "chave SSH não encontrada em $KeyFile. Ajuste SSH_KEY no infra\.env." }

$Ip = & terraform "-chdir=$Infra" output -raw public_ip 2>$null
if ($LASTEXITCODE -eq 0) { $EnvLines = & terraform "-chdir=$Infra" output -raw deploy_env 2>$null }
if ($LASTEXITCODE -ne 0 -or -not $Ip -or -not $EnvLines) { Fail "sem os outputs do Terraform. Rode 'terraform -chdir=infra apply' antes." }

$Hf = Cfg 'HF_TOKEN'
if (-not $Hf) { Fail 'preencha HF_TOKEN no infra\.env' }

# Cópia da chave com permissão restrita: o ssh recusa chave "aberta" demais.
New-Item -ItemType Directory -Force -Path $Deploy | Out-Null
$Key = Join-Path $Deploy 'key.pem'
Copy-Item -Force $KeyFile $Key
& icacls $Key /inheritance:r /grant:r "$($env:USERNAME):(F)" | Out-Null
$SshArgs = @(
    '-i', $Key, '-o', 'StrictHostKeyChecking=accept-new',
    '-o', "UserKnownHostsFile=$((Join-Path $Deploy 'known_hosts').Replace('\', '/'))",
    '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=30', '-o', 'LogLevel=ERROR'
)
$Target = "ubuntu@$Ip"

if (& git -C $Infra status --porcelain) { Write-Host 'AVISO: há alterações não commitadas; só o que está no HEAD é enviado.' -ForegroundColor Yellow }
# autocrlf desligado: no Windows o pacote sairia com CRLF e quebraria os scripts.
$Tar = Join-Path $Deploy 'app.tar'
& git -c core.autocrlf=false -C (Split-Path -Parent $Infra) archive --format=tar -o $Tar HEAD `
    backend frontend db infra/docker-compose.aws.yml infra/remote-deploy.sh
if ($LASTEXITCODE -ne 0) { Fail 'git archive falhou. A pasta infra já foi commitada?' }

Write-Host 'Aguardando a EC2 aceitar SSH e terminar o bootstrap (Docker)...'
$ready = $false
for ($i = 0; $i -lt 120 -and -not $ready; $i++) {
    & ssh @SshArgs $Target 'test -f /opt/autoitil/.bootstrap-done' 2>$null
    if ($LASTEXITCODE -eq 0) { $ready = $true } else { Start-Sleep -Seconds 5 }
}
if (-not $ready) { Fail "a EC2 não ficou pronta em 10 min. Seu IP mudou? Rode 'terraform -chdir=infra apply'." }

Write-Host "Enviando $(& git -C $Infra rev-parse --short HEAD) para $Target..."
& scp -C @SshArgs $Tar "${Target}:/opt/autoitil/app.tar"
if ($LASTEXITCODE -ne 0) { Fail 'scp do pacote falhou' }
# Os segredos vão num arquivo temporário (UTF-8 sem BOM, LF) para a RAM da EC2:
# nunca na linha de comando. O pipe do PowerShell para o ssh estraga a codificação.
$Secrets = Join-Path $Deploy 'input.tmp'
$text = (@($EnvLines) + "HF_TOKEN=$Hf", "ADMIN_EMAIL=$(Cfg 'ADMIN_EMAIL')", "ADMIN_PASSWORD=$(Cfg 'ADMIN_PASSWORD')") -join "`n"
[IO.File]::WriteAllText($Secrets, "$text`n", (New-Object System.Text.UTF8Encoding($false)))
& scp @SshArgs $Secrets "${Target}:/dev/shm/autoitil-input"
$scpCode = $LASTEXITCODE
Remove-Item -Force $Secrets
if ($scpCode -ne 0) { Fail 'scp dos segredos falhou' }
& ssh @SshArgs $Target 'cd /opt/autoitil && tar -xf app.tar --strip-components=1 infra/remote-deploy.sh && bash remote-deploy.sh start'
if ($LASTEXITCODE -ne 0) { Fail 'não consegui iniciar o deploy na EC2' }

# Acompanha o log. Se o SSH cair (255), o deploy continua na EC2: reconecta.
$from = '+1'; $code = 255
for ($i = 0; $i -lt 30 -and $code -eq 255; $i++) {
    & ssh @SshArgs $Target "bash /opt/autoitil/remote-deploy.sh follow $from"
    $code = $LASTEXITCODE
    if ($code -eq 255) { Write-Host '(conexão caiu, reconectando...)' -ForegroundColor Yellow; $from = '20'; Start-Sleep -Seconds 5 }
}
if ($code -ne 0) { Fail "o deploy falhou (código $code). Log na EC2: /opt/autoitil/deploy.log" }

Write-Host ''
Write-Host "AutoITIL no ar: http://$Ip" -ForegroundColor Green
