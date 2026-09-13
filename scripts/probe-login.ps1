[Console]::OutputEncoding = [Text.Encoding]::UTF8
$loginPhone = $env:SHINKOU_LOGIN_PHONE
$loginPassword = $env:SHINKOU_LOGIN_PASSWORD
$captchaCode = $env:SHINKOU_CAPTCHA_CODE
if ([string]::IsNullOrWhiteSpace($loginPhone) -or [string]::IsNullOrWhiteSpace($loginPassword) -or [string]::IsNullOrWhiteSpace($captchaCode)) {
  throw '请先设置 SHINKOU_LOGIN_PHONE、SHINKOU_LOGIN_PASSWORD 和 SHINKOU_CAPTCHA_CODE 环境变量。'
}
$jar = 'C:\Users\Lenovo\Desktop\Shinkou\cj.txt'
$token = (Get-Content 'C:\Users\Lenovo\Desktop\Shinkou\xsrf-token.txt' -Raw).Trim()
$cid = (Get-Content 'C:\Users\Lenovo\Desktop\Shinkou\captcha-id.txt' -Raw).Trim()
$body = @{ phoneNumber = $loginPhone; password = $loginPassword; captchaId = $cid; captcha = $captchaCode } | ConvertTo-Json
& curl.exe -s -w '\nHTTP:%{http_code}' -b $jar -c $jar -X POST 'http://localhost:8080/auth/login/password' -H 'Content-Type: application/json' -H "X-XSRF-TOKEN: $token" -d $body
Write-Output ''
Write-Output '=== now without XSRF header ==='
& curl.exe -s -w '\nHTTP:%{http_code}' -b $jar -c $jar -X POST 'http://localhost:8080/auth/login/password' -H 'Content-Type: application/json' -d $body
