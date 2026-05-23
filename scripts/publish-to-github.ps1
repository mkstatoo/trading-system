# پس از ساخت ریپوی خالی trading-system در https://github.com/new اجرا کنید:
#   git remote remove origin 2>$null
#   git remote add origin https://github.com/mkstatoo/trading-system.git
#   git push -u origin main

$ErrorActionPreference = "Stop"
Set-Location (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
if (-not (Test-Path ".git")) { git init; git branch -M main }
git add -A
git status
git commit -m "Update trading-system" 2>$null
git remote remove origin 2>$null
git remote add origin https://github.com/mkstatoo/trading-system.git
git push -u origin main
