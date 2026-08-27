param($Port=3000)
$cd = "C:\pdf-toolkit\frontend"
Set-Location $cd
& .\node_modules\.bin\next dev --hostname localhost > frontend_dev.log 2>&1