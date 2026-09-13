$b64 = Get-Content 'c:\Users\Lenovo\Desktop\Shinkou\Shinkou Insight\scripts\browser-captcha.b64' -Raw
[IO.File]::WriteAllBytes('C:\Users\Lenovo\Desktop\Shinkou\browser-captcha.png', [Convert]::FromBase64String($b64.Trim()))
Write-Output 'SAVED'
