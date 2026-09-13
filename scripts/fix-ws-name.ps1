[Console]::OutputEncoding = [Text.Encoding]::UTF8
$base = 'http://localhost:8080'
$jar = 'C:\Users\Lenovo\Desktop\Shinkou\cj2.txt'
$cookieToken = ((Get-Content $jar) | Where-Object { $_ -match 'XSRF-TOKEN' } | Select-Object -Last 1) -split "`t" | Select-Object -Last 1

# PS 5.1 读无 BOM 脚本为 ANSI，中文会乱码，改用 \u 转义（Jackson 服务端解析）
$json = '{"name":"admin \u7684\u5de5\u4f5c\u533a","code":"ws-1npxrj1ldds0"}'
[IO.File]::WriteAllText('C:\Users\Lenovo\Desktop\Shinkou\ws-body.json', $json, [Text.Encoding]::ASCII)

$wsId = '218347600795029504'
$patchOut = & curl.exe -s -w '\nHTTP:%{http_code}' -b $jar -c $jar -X PATCH "$base/workspaces/$wsId" -H 'Content-Type: application/json' -H "X-XSRF-TOKEN: $cookieToken" --data-binary '@C:\Users\Lenovo\Desktop\Shinkou\ws-body.json'
Write-Output $patchOut
