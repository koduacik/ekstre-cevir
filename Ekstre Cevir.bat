@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
rem Ekstre Cevir - PDF dosyasini bu simgenin ustune birakin.
rem Ilk calistirmada bu klasore .venv kurar; sonra PDF'i cevirip Excel'i acar.

set "KLASOR=%~dp0"
set "VENV=%KLASOR%.venv"
set "LOG=%KLASOR%.kurulum.log"
set "PYTHONIOENCODING=utf-8"

if "%~1"=="" goto kullanim

call :kurulum
if errorlevel 1 goto bekle_cik

set "HATA=0"
:dongu
if "%~1"=="" goto bitti
call :cevir "%~1"
if errorlevel 1 set "HATA=1"
shift
goto dongu

:bitti
if "%HATA%"=="1" goto bekle_cik
exit /b 0

:kullanim
echo PDF dosyasını "Ekstre Cevir" simgesinin üstüne sürükleyip bırakın.
pause
exit /b 1

:bekle_cik
echo.
pause
exit /b 1

rem ---------------------------------------------------------------------------
:cevir
rem --yol yalnızca üretilen Excel dosyasının yolunu yazar; hata mesajı ekrana düşer.
rem Yol geçici dosyadan okunur: for /f, "Ekstre (1).pdf" gibi parantezli adlarda bozuluyor.
set "CIKTI="
set "YOL_DOSYASI=%TEMP%\ekstre_cevir_%RANDOM%%RANDOM%.txt"
"%VENV%\Scripts\python.exe" "%KLASOR%ekstre_cevir.py" --yol "%~1" >"%YOL_DOSYASI%"
if errorlevel 1 goto cevir_hata
set /p CIKTI=<"%YOL_DOSYASI%"
del "%YOL_DOSYASI%" >nul 2>&1
if not defined CIKTI goto cevir_hata
start "" "%CIKTI%"
exit /b 0

:cevir_hata
del "%YOL_DOSYASI%" >nul 2>&1
echo.
echo "%~nx1" çevrilemedi.
exit /b 1

rem ---------------------------------------------------------------------------
:kurulum
if not exist "%VENV%\Scripts\python.exe" goto kur
"%VENV%\Scripts\python.exe" -c "import pdfplumber, openpyxl" >nul 2>&1
if errorlevel 1 goto kur
fc /b "%KLASOR%requirements.txt" "%VENV%\.kurulum_tamam" >nul 2>&1
if errorlevel 1 goto kur
exit /b 0

:kur
echo İlk kullanım: gerekli bileşenler kuruluyor (internet gerekir, 1-2 dakika sürebilir)...
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if defined PY goto python_var
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=python"
if defined PY goto python_var
echo.
echo Python 3.9 veya üstü bulunamadı.
echo python.org/downloads adresinden Python'u kurun; kurulumda "Add python.exe to PATH" kutusunu işaretleyin.
exit /b 1

:python_var
if exist "%VENV%" rmdir /s /q "%VENV%"
%PY% -m venv "%VENV%" >>"%LOG%" 2>&1
if errorlevel 1 goto kurulum_hata
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check -r "%KLASOR%requirements.txt" >>"%LOG%" 2>&1
if errorlevel 1 goto kurulum_hata
copy /y "%KLASOR%requirements.txt" "%VENV%\.kurulum_tamam" >nul
exit /b 0

:kurulum_hata
echo.
echo Gerekli bileşenler kurulamadı. İnternet bağlantınızı kontrol edip tekrar deneyin.
echo Ayrıntılar: %LOG%
exit /b 1
