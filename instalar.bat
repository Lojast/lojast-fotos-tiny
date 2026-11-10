@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Criando ambiente Python...
py -3 -m venv .venv || goto erro
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || goto erro
python -m playwright install chromium || goto erro
if not exist .env copy .env.example .env
echo.
echo Pronto. Agora: 1) abra o arquivo .env e preencha o TINY_TOKEN e os links do repositorio de fotos
echo               2) coloque a logo em assets\logo_lojast.png
echo               3) de dois cliques em rodar.bat
pause
exit /b 0
:erro
echo Algo deu errado na instalacao. Verifique se o Python 3.10+ e o Git estao instalados.
pause
exit /b 1
