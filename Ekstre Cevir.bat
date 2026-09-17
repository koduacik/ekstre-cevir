@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo PDF banka ekstresini bu dosyanin uzerine surukleyip birak.
  echo Excel dosyasi PDF'in yanina kaydedilir ve acilir.
  pause
  exit /b
)
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python bulunamadi. python.org/downloads adresinden kur ve "Add python.exe to PATH" kutusunu isaretle.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Ilk acilis: gerekli bilesenler kuruluyor. Bu yalniz bir kez olur...
  %PY% -m venv .venv || goto :hata
  ".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt || goto :hata
)
for %%F in (%*) do (
  ".venv\Scripts\python.exe" ekstre_cevir.py "%%~fF"
  if exist "%%~dpnF_ekstre.xlsx" start "" "%%~dpnF_ekstre.xlsx"
)
pause
exit /b
:hata
echo Kurulum basarisiz oldu.
pause
exit /b 1
