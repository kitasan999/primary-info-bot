@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  Discord Webhook 設定（.env を作る）
echo ========================================
echo.
echo  Discord でコピーした Webhook URL を
echo  この画面に貼り付けて Enter を押してください。
echo.
echo  （例）https://discord.com/api/webhooks/123456789/abcdef...
echo.

set /p WEBHOOK=Webhook URL: 

if "%WEBHOOK%"=="" (
  echo.
  echo URL が空です。もう一度やり直してください。
  pause
  exit /b 1
)

echo DISCORD_WEBHOOK_URL=%WEBHOOK%> .env

echo.
echo .env ファイルを作成しました！
echo.
echo Discord にテスト通知を送ります…
echo.

python main.py --test

echo.
pause
