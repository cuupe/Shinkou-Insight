$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Text.Encoding]::UTF8
$base = 'http://localhost:8080'
$jar = 'C:\Users\Lenovo\Desktop\Shinkou\cj.txt'

# 1. CSRF：token 为 BREACH 编码值，必须用响应体里的 token 而非 cookie 原值
$csrfJson = & curl.exe -s -c $jar -b $jar "$base/auth/csrf"
$token = (($csrfJson | ConvertFrom-Json).data.token)
$token | Out-File 'C:\Users\Lenovo\Desktop\Shinkou\xsrf-token.txt' -Encoding ascii -NoNewline

# 2. captcha
$capJson = & curl.exe -s -c $jar -b $jar "$base/auth/captcha"
$cap = ($capJson | ConvertFrom-Json).data
$cap.captchaId | Out-File 'C:\Users\Lenovo\Desktop\Shinkou\captcha-id.txt' -Encoding ascii -NoNewline
$prefix = 'data:image/png;base64,'
$b64 = $cap.imgUrl
if ($b64.StartsWith($prefix)) { $b64 = $b64.Substring($prefix.Length) }
[IO.File]::WriteAllBytes('C:\Users\Lenovo\Desktop\Shinkou\captcha.png', [Convert]::FromBase64String($b64))
Write-Output 'CAPTCHA-READY'
