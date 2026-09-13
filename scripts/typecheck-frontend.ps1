Set-Location 'c:\Users\Lenovo\Desktop\Shinkou\Shinkou Insight\apps\web'
& npx vue-tsc --noEmit -p tsconfig.app.json *> tsc.log
Write-Output ("EXIT=" + $LASTEXITCODE)
Get-Content tsc.log
