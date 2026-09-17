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

Set-Location $Root
& $Java -jar "$Root\litemall-wx-api\target\litemall-wx-api-0.1.0-exec.jar" `
  --server.port=8080 `
  --demo.mode.enabled=true `
  --demo.payment.enabled=true `
  --demo.shipping.enabled=true
