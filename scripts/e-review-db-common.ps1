function Get-EReviewProjectRoot {
  param([string]$Root = "")
  if ($Root) {
    return (Resolve-Path $Root).Path
  }
  $scriptDir = Split-Path -Parent $MyInvocation.ScriptName
  return (Resolve-Path (Join-Path $scriptDir "..")).Path
}

function Get-EReviewDbConfig {
  param(
    [string]$Root = "",
    [string]$MysqlUser = "",
    [string]$MysqlPassword = "",
    [string]$MysqlDatabase = "litemall"
  )

  $projectRoot = Get-EReviewProjectRoot -Root $Root
  $dbConfigPath = Join-Path $projectRoot "litemall-db\src\main\resources\application-db.yml"
  $configText = if (Test-Path $dbConfigPath) { Get-Content -LiteralPath $dbConfigPath -Raw } else { "" }

  if (-not $MysqlUser) {
    if ($env:EREVIEW_MYSQL_USER) {
      $MysqlUser = $env:EREVIEW_MYSQL_USER
    } elseif ($configText -match '(?m)^\s*username:\s*([^\r\n]+)\s*$') {
      $MysqlUser = $Matches[1].Trim()
    } else {
      $MysqlUser = "litemall"
    }
  }

  if (-not $MysqlPassword) {
    if ($env:EREVIEW_MYSQL_PASSWORD) {
      $MysqlPassword = $env:EREVIEW_MYSQL_PASSWORD
    } elseif ($env:MYSQL_PWD) {
      $MysqlPassword = $env:MYSQL_PWD
    } elseif ($configText -match '(?m)^\s*password:\s*([^\r\n]+)\s*$') {
      $MysqlPassword = $Matches[1].Trim()
    }
  }

  if (-not $MysqlPassword) {
    throw "MySQL password not provided. Set EREVIEW_MYSQL_PASSWORD or pass -MysqlPassword."
  }

  [ordered]@{
    Root = $projectRoot
    User = $MysqlUser
    Password = $MysqlPassword
    Database = $MysqlDatabase
  }
}

function Invoke-EReviewMysql {
  param(
    [hashtable]$Db,
    [string]$Sql,
    [switch]$Raw
  )

  $previous = $env:MYSQL_PWD
  try {
    $env:MYSQL_PWD = $Db.Password
    $args = @("-u$($Db.User)", "-D", $Db.Database, "-e", $Sql)
    if ($Raw) {
      $args = @("-u$($Db.User)", "-N", "-D", $Db.Database, "-e", $Sql)
    }
    $output = & mysql @args
    if ($LASTEXITCODE -ne 0) {
      throw "mysql command failed"
    }
    return $output
  } finally {
    $env:MYSQL_PWD = $previous
  }
}

function Invoke-EReviewMysqlFile {
  param(
    [hashtable]$Db,
    [string]$SqlFile
  )

  if (-not (Test-Path -LiteralPath $SqlFile)) {
    throw "SQL file not found"
  }

  $previous = $env:MYSQL_PWD
  try {
    $env:MYSQL_PWD = $Db.Password
    Get-Content -LiteralPath $SqlFile -Raw | & mysql "-u$($Db.User)" $Db.Database
    if ($LASTEXITCODE -ne 0) {
      throw "mysql restore failed"
    }
  } finally {
    $env:MYSQL_PWD = $previous
  }
}
