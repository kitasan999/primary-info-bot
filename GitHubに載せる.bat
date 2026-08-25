@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  GitHub に載せる（自動セットアップ）
echo ========================================
echo.

REM --- .env があるか確認 ---
if not exist ".env" (
  echo .env がありません。先に Webhook設定.bat を実行してください。
  pause
  exit /b 1
)

REM --- GitHub ユーザー名を聞く ---
echo GitHub のユーザー名を入力してください。
echo （例）myusername  ※ https://github.com/ の後ろの名前
echo.
set /p GH_USER=ユーザー名: 

if "%GH_USER%"=="" (
  echo ユーザー名が空です。
  pause
  exit /b 1
)

set REPO_NAME=primary-info-bot
set REPO_URL=https://github.com/%GH_USER%/%REPO_NAME%.git

echo.
echo ========================================
echo  手順1: GitHub で空のリポジトリを作る
echo ========================================
echo.
echo  ブラウザが開きます。次の設定で「Create repository」を押してください：
echo    - Repository name: %REPO_NAME%
echo    - Public または Private（どちらでもOK）
echo    - README / .gitignore / license は全部チェック OFF
echo.
pause
start "" "https://github.com/new?name=%REPO_NAME%&description=MHLW+news+bot"

echo.
echo  リポジトリを作成したら Enter を押してください...
pause >nul

echo.
echo ========================================
echo  手順2: コードをアップロード（push）
echo ========================================
echo.

git remote remove origin 2>nul
git remote add origin %REPO_URL%

echo push 中...（GitHub ログインを求められたら許可してください）
git push -u origin main

if errorlevel 1 (
  echo.
  echo push に失敗しました。
  echo  - リポジトリ名が %REPO_NAME% か確認
  echo  - GitHub にログインできているか確認
  pause
  exit /b 1
)

echo.
echo push 成功！
echo.

echo ========================================
echo  手順3: Discord Webhook を Secret に登録
echo ========================================
echo.

REM .env から URL を読み取り（表示はマスク）
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
  if /i "%%A"=="DISCORD_WEBHOOK_URL" set WEBHOOK=%%B
)

echo  ブラウザで Secrets 設定ページを開きます。
echo  「New repository secret」を押して：
echo    Name:  DISCORD_WEBHOOK_URL
echo    Secret: （クリップボードにコピー済み）
echo.

echo %WEBHOOK%| clip
echo  Webhook URL をクリップボードにコピーしました。
echo  GitHub の Secret 欄に Ctrl+V で貼り付けてください。
echo.
pause
start "" "https://github.com/%GH_USER%/%REPO_NAME%/settings/secrets/actions/new?name=DISCORD_WEBHOOK_URL"

echo.
echo ========================================
echo  手順4: Actions を手動テスト
echo ========================================
echo.
echo  Secret 保存後、Enter を押すと Actions ページを開きます。
echo  「厚労省 新着チェック」→ Run workflow を押してください。
echo.
pause
start "" "https://github.com/%GH_USER%/%REPO_NAME%/actions"

echo.
echo 完了！ あとは1時間ごとに自動実行されます。
echo.
pause
