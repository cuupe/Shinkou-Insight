$ErrorActionPreference = 'Stop'
$base = 'http://localhost:8080'
$loginPhone = $env:SHINKOU_LOGIN_PHONE
$loginPassword = $env:SHINKOU_LOGIN_PASSWORD
if ([string]::IsNullOrWhiteSpace($loginPhone) -or [string]::IsNullOrWhiteSpace($loginPassword)) {
  throw '请先设置 SHINKOU_LOGIN_PHONE 和 SHINKOU_LOGIN_PASSWORD 环境变量。'
}
$s = New-Object Microsoft.PowerShell.Commands.WebRequestSession

# 1. CSRF
Invoke-WebRequest -Uri "$base/auth/csrf" -WebSession $s -UseBasicParsing | Out-Null

# 2. captcha
$cap = Invoke-RestMethod -Uri "$base/auth/captcha" -WebSession $s
$cap.data.captchaId | Out-File 'C:\Users\Lenovo\Desktop\Shinkou\captcha-id.txt' -Encoding ascii
$prefix = 'data:image/png;base64,'
$b64 = $cap.data.imgUrl
if ($b64.StartsWith($prefix)) { $b64 = $b64.Substring($prefix.Length) }
[IO.File]::WriteAllBytes('C:\Users\Lenovo\Desktop\Shinkou\captcha.png', [Convert]::FromBase64String($b64))

# 3. login
$code = Get-Content 'C:\Users\Lenovo\Desktop\Shinkou\captcha-code.txt' -Raw
$code = $code.Trim()
$xsrf = ($s.Cookies.GetCookies("$base/") | Where-Object { $_.Name -eq 'XSRF-TOKEN' } | Select-Object -First 1).Value
$body = @{
  phoneNumber = $loginPhone
  password = $loginPassword
  captchaId = $cap.data.captchaId
  captcha = $code
} | ConvertTo-Json
try {
  $login = Invoke-RestMethod -Uri "$base/auth/login/password" -Method POST -WebSession $s -ContentType 'application/json' -Body $body -Headers @{ 'X-XSRF-TOKEN' = $xsrf }
  ($login | ConvertTo-Json -Depth 5) | Out-File 'C:\Users\Lenovo\Desktop\Shinkou\login-result.json' -Encoding utf8
} catch {
  $_.Exception.Message | Out-File 'C:\Users\Lenovo\Desktop\Shinkou\login-result.json' -Encoding utf8
  exit
}

# 4. workspaces/my
$my = Invoke-RestMethod -Uri "$base/workspaces/my" -WebSession $s
($my | ConvertTo-Json -Depth 5) | Out-File 'C:\Users\Lenovo\Desktop\Shinkou\ws-my.json' -Encoding utf8

# 5. create workspace if empty
if (@($my.data).Count -eq 0 -or $my.data -eq $null) {
  $xsrf2 = ($s.Cookies.GetCookies("$base/") | Where-Object { $_.Name -eq 'XSRF-TOKEN' } | Select-Object -First 1).Value
  $wbody = @{ name = 'admin 的工作区' } | ConvertTo-Json
  $created = Invoke-RestMethod -Uri "$base/workspaces" -Method POST -WebSession $s -ContentType 'application/json' -Body $wbody -Headers @{ 'X-XSRF-TOKEN' = $xsrf2 }
  ($created | ConvertTo-Json -Depth 5) | Out-File 'C:\Users\Lenovo\Desktop\Shinkou\ws-created.json' -Encoding utf8
}
