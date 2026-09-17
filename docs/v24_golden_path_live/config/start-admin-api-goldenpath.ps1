$ErrorActionPreference = "Stop"

$Root = "D:\EReviewAgent\litemall-v24-goldenpath"
$Java = "D:\developtool\jdk-21.0.10\bin\java.exe"
$EnvFile = Join-Path $Root ".env.goldenpath.local"
$Vars = @{}
Get-Content -LiteralPath $EnvFile | ForEach-Object {
  if ($_ -match "^([^#=]+)=(.*)$") {
    $Vars[$matches[1]] = $matches[2]
  }
}

$env:SPRING_DATASOURCE_DRUID_URL = "jdbc:mysql://$($Vars['MYSQL_HOST']):$($Vars['MYSQL_PORT'])/$($Vars['MYSQL_DATABASE'])?useUnicode=true&characterEncoding=UTF-8&serverTimezone=UTC&useSSL=false&allowPublicKeyRetrieval=true"
$env:SPRING_DATASOURCE_DRUID_USERNAME = $Vars["MYSQL_USER"]
$env:SPRING_DATASOURCE_DRUID_PASSWORD = $Vars["MYSQL_PWD"]
$env:E_REVIEW_AI_READ_TIMEOUT_MS = "180000"

Set-Location $Root
& $Java -jar "$Root\litemall-admin-api\target\litemall-admin-api-0.1.0-exec.jar" `
  --server.port=8083 `
  --ai.patrol.enabled=false `
  --ai.patrol.batch-size=1 `
  --ai.patrol.fixed-delay=600000 `
  --ai.patrol.scan-demo-review=false `
  --ai.patrol.scan-litemall-comment=true `
  --ai.service.base-url=http://127.0.0.1:8008 `
  --agent-rag.enabled=true `
  --agent-rag.base-url=http://127.0.0.1:8008 `
  --agent-rag.read-timeout-ms=180000 `
  --agent-rag.total-timeout-ms=190000 `
  --demo.agent-framework.enabled=true `
  --demo.agent-framework.prefer-framework-trace=true `
  --demo.agent-framework.fallback-to-legacy=false
