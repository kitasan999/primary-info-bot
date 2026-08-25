@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  厚労省ボット - テストメニュー
echo ========================================
echo.
echo  1. デモ通知（最新記事1件・Discord不要でも画面に表示）
echo  2. Discordテスト（Webhook URL が必要）
echo  3. 通常実行（新着チェック）
echo.
set /p choice=番号を入力 (1/2/3): 

if "%choice%"=="1" (
  python main.py --demo
  goto end
)
if "%choice%"=="2" (
  python main.py --test
  goto end
)
if "%choice%"=="3" (
  python main.py
  goto end
)

echo 1, 2, 3 のどれかを入力してください。

:end
echo.
pause
