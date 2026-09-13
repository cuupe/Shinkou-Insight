Stop-Process -Id 27672 -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Set-Location 'c:\Users\Lenovo\Desktop\Shinkou\Shinkou Insight\apps\backend'
& mvn spring-boot:run -o *> backend-run.log
