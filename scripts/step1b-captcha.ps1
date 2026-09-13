[Console]::OutputEncoding = [Text.Encoding]::UTF8
$jar = 'C:\Users\Lenovo\Desktop\Shinkou\cj2.txt'
Remove-Item $jar -ErrorAction SilentlyContinue
$base = 'http://localhost:8080'

# fresh csrf + captcha in one jar
$csrf = & curl.exe -s -c $jar -b $jar "$base/auth/csrf"
$capJson = & curl.exe -s -c $jar -b $jar "$base/auth/captcha"
$cap = ($capJson | ConvertFrom-Json).data
$prefix = 'data:image/png;base64,'
$b64 = $cap.imgUrl
if ($b64.StartsWith($prefix)) { $b64 = $b64.Substring($prefix.Length) }
[IO.File]::WriteAllBytes('C:\Users\Lenovo\Desktop\Shinkou\captcha2.png', [Convert]::FromBase64String($b64))
$cap.captchaId | Out-File 'C:\Users\Lenovo\Desktop\Shinkou\captcha2-id.txt' -Encoding ascii -NoNewline
Write-Output 'CAPTCHA2-READY'
Write-Output "cookies in jar:"
Get-Content $jar | Where-Object { $_ -notmatch '^#' }
