$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Text.Encoding]::UTF8
$base = 'http://localhost:8080'
$loginPhone = $env:SHINKOU_LOGIN_PHONE
$loginPassword = $env:SHINKOU_LOGIN_PASSWORD
if ([string]::IsNullOrWhiteSpace($loginPhone) -or [string]::IsNullOrWhiteSpace($loginPassword)) {
  throw '请先设置 SHINKOU_LOGIN_PHONE 和 SHINKOU_LOGIN_PASSWORD 环境变量。'
}
$jar = 'C:\Users\Lenovo\Desktop\Shinkou\cj.txt'
$token = (Get-Content 'C:\Users\Lenovo\Desktop\Shinkou\xsrf-token.txt' -Raw).Trim()
$captchaId = (Get-Content 'C:\Users\Lenovo\Desktop\Shinkou\captcha-id.txt' -Raw).Trim()
$code = (Get-Content 'C:\Users\Lenovo\Desktop\Shinkou\captcha-code.txt' -Raw).Trim()

$body = @{
  phoneNumber = $loginPhone
  password = $loginPassword
  captchaId = $captchaId
  captcha = $code
} | ConvertTo-Json

$loginOut = & curl.exe -s -w '\n%{http_code}' -c $jar -b $jar -X POST "$base/auth/login/password" -H 'Content-Type: application/json' -H "X-XSRF-TOKEN: $token" -d $body
$loginOut | Out-File 'C:\Users\Lenovo\Desktop\Shinkou\login-result.json' -Encoding utf8
Write-Output $loginOut

$myOut = & curl.exe -s -c $jar -b $jar "$base/workspaces/my"
$myOut | Out-File 'C:\Users\Lenovo\Desktop\Shinkou\ws-my.json' -Encoding utf8

$my = $myOut | ConvertFrom-Json
$list = @($my.data)
if ($list.Count -eq 0) {
  $wbody = @{ name = 'admin 的工作区' } | ConvertTo-Json
  $createdOut = & curl.exe -s -c $jar -b $jar -X POST "$base/workspaces" -H 'Content-Type: application/json' -H "X-XSRF-TOKEN: $token" -d $wbody
  $createdOut | Out-File 'C:\Users\Lenovo\Desktop\Shinkou\ws-created.json' -Encoding utf8
  Write-Output $createdOut
}
Write-Output 'DONE'
