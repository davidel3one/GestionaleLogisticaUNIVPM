# Da eseguire su Windows (PyInstaller non compila incrociato tra piattaforme):
# lo stesso gestionale.spec produce un eseguibile Windows se lanciato qui.
Set-Location "$PSScriptRoot\.."

uv run pyinstaller packaging/gestionale.spec `
    --distpath dist/windows `
    --workpath build/windows `
    --noconfirm

Write-Host "Build completata: dist/windows/GestionaleLogistica/GestionaleLogistica.exe"
