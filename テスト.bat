@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  厚労省ボット - テストメニュー
echo ========================================
echo.
echo  1. デモ通知（最新1件をDiscordへ）
echo  2. Discord接続テスト
echo  3. 通常実行（新着チェック）
echo  4. プレビュー（Discord送らず内容確認）
echo  5. まとめ通知デモ
echo  6. お金系デモ（金融庁・日銀・財務省）
echo.
set /p choice=番号を入力 (1-6): 

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
if "%choice%"=="4" (
  python main.py --preview
  goto end
)
if "%choice%"=="5" (
  python main.py --demo-digest
  goto end
)
if "%choice%"=="6" (
  python main.py --demo-money
  goto end
)

echo 1〜6 のどれかを入力してください。

:end
echo.
pause
