@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  Gemini API キー設定（.env に追加）
echo ========================================
echo.
echo  1. ブラウザで https://aistudio.google.com/apikey を開く
echo  2. 「APIキーを作成」を押してコピー
echo  3. この画面に貼り付けて Enter
echo.

set /p GEMINI_KEY=Gemini APIキー: 

if "%GEMINI_KEY%"=="" (
  echo キーが空です。
  pause
  exit /b 1
)

if exist ".env" (
  findstr /V /I "GEMINI_API_KEY" .env > .env.tmp
  move /Y .env.tmp .env >nul
) else (
  echo. > .env
)

echo GEMINI_API_KEY=%GEMINI_KEY%>> .env

echo.
echo .env に GEMINI_API_KEY を保存しました！
echo デモ通知で AI 要約を試します…
echo.

python main.py --demo

echo.
pause
