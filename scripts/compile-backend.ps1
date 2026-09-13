Set-Location 'c:\Users\Lenovo\Desktop\Shinkou\Shinkou Insight\apps\backend'
& mvn compile -o *> mvn-compile.log
Write-Output ("EXIT=" + $LASTEXITCODE)
Get-Content mvn-compile.log -Tail 25
