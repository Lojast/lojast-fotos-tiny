@echo off
chcp 65001 >nul
cd /d "%~dp0"
call .venv\Scripts\activate.bat
rem Deixe esta janela aberta e o PC ligado (sem suspender) enquanto roda.
rem Sem argumentos = SIMULACAO. Para gravar de verdade:  rodar.bat --gravar
python -m fotos_tiny %*
pause
