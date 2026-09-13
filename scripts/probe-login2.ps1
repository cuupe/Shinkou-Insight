[Console]::OutputEncoding = [Text.Encoding]::UTF8
$loginPhone = $env:SHINKOU_LOGIN_PHONE
$loginPassword = $env:SHINKOU_LOGIN_PASSWORD
$captchaCode = $env:SHINKOU_CAPTCHA_CODE
if ([string]::IsNullOrWhiteSpace($loginPhone) -or [string]::IsNullOrWhiteSpace($loginPassword) -or [string]::IsNullOrWhiteSpace($captchaCode)) {
  throw '请先设置 SHINKOU_LOGIN_PHONE、SHINKOU_LOGIN_PASSWORD 和 SHINKOU_CAPTCHA_CODE 环境变量。'
}
$jar = 'C:\Users\Lenovo\Desktop\Shinkou\cj.txt'
$cookieToken = ((Get-Content $jar) | Where-Object { $_ -match 'XSRF-TOKEN' } | Select-Object -Last 1) -split "`t" | Select-Object -Last 1
$cid = (Get-Content 'C:\Users\Lenovo\Desktop\Shinkou\captcha-id.txt' -Raw).Trim()
$body = @{ phoneNumber = $loginPhone; password = $loginPassword; captchaId = $cid; captcha = $captchaCode } | ConvertTo-Json
Write-Output "=== using cookie raw value: $cookieToken ==="
& curl.exe -s -w '\nHTTP:%{http_code}' -b $jar -X POST 'http://localhost:8080/auth/login/password' -H 'Content-Type: application/json' -H "X-XSRF-TOKEN: $cookieToken" -d $body
Write-Output ''
Write-Output '=== GET a protected endpoint (no csrf needed) ==='
& curl.exe -s -w '\nHTTP:%{http_code}' -b $jar 'http://localhost:8080/auth/me'
