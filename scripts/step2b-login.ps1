[Console]::OutputEncoding = [Text.Encoding]::UTF8
$loginPhone = $env:SHINKOU_LOGIN_PHONE
$loginPassword = $env:SHINKOU_LOGIN_PASSWORD
if ([string]::IsNullOrWhiteSpace($loginPhone) -or [string]::IsNullOrWhiteSpace($loginPassword)) {
  throw '请先设置 SHINKOU_LOGIN_PHONE 和 SHINKOU_LOGIN_PASSWORD 环境变量。'
}
$base = 'http://localhost:8080'
$jar = 'C:\Users\Lenovo\Desktop\Shinkou\cj2.txt'
$cookieToken = ((Get-Content $jar) | Where-Object { $_ -match 'XSRF-TOKEN' } | Select-Object -Last 1) -split "`t" | Select-Object -Last 1
$cid = (Get-Content 'C:\Users\Lenovo\Desktop\Shinkou\captcha2-id.txt' -Raw).Trim()
$code = (Get-Content 'C:\Users\Lenovo\Desktop\Shinkou\captcha2-code.txt' -Raw).Trim()

$body = @{ phoneNumber = $loginPhone; password = $loginPassword; captchaId = $cid; captcha = $code } | ConvertTo-Json
[IO.File]::WriteAllText('C:\Users\Lenovo\Desktop\Shinkou\login-body.json', $body, [Text.UTF8Encoding]::new($false))

$loginOut = & curl.exe -s -w '\nHTTP:%{http_code}' -c $jar -b $jar -X POST "$base/auth/login/password" -H 'Content-Type: application/json' -H "X-XSRF-TOKEN: $cookieToken" -d '@C:\Users\Lenovo\Desktop\Shinkou\login-body.json'
Write-Output $loginOut

$myOut = & curl.exe -s -c $jar -b $jar "$base/workspaces/my"
Write-Output '=== workspaces/my ==='
Write-Output $myOut

$my = $myOut | ConvertFrom-Json
$list = @($my.data)
if ($list.Count -eq 0) {
  $wbody = @{ name = 'admin 的工作区' } | ConvertTo-Json
  [IO.File]::WriteAllText('C:\Users\Lenovo\Desktop\Shinkou\ws-body.json', $wbody, [Text.UTF8Encoding]::new($false))
  $createdOut = & curl.exe -s -c $jar -b $jar -X POST "$base/workspaces" -H 'Content-Type: application/json' -H "X-XSRF-TOKEN: $cookieToken" -d '@C:\Users\Lenovo\Desktop\Shinkou\ws-body.json'
  Write-Output '=== created ==='
  Write-Output $createdOut
  [IO.File]::WriteAllText('C:\Users\Lenovo\Desktop\Shinkou\ws-created.json', $createdOut, [Text.UTF8Encoding]::new($false))
}
[IO.File]::WriteAllText('C:\Users\Lenovo\Desktop\Shinkou\ws-my.json', $myOut, [Text.UTF8Encoding]::new($false))
Write-Output 'DONE'
