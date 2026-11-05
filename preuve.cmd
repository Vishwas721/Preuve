@echo off
rem ============================================================================================
rem  Preuve - one command to run everything (Windows).
rem
rem    preuve              start the app (production stack)  ->  http://localhost:3100
rem    preuve dev          start the development setup (API, worker, web in their own windows)
rem    preuve stop         stop the app (add "dev" to stop the development containers too)
rem    preuve status       show what's running and whether it's healthy
rem    preuve logs         follow the app's logs (Ctrl+C to stop)
rem    preuve update       pull the latest CI-built version, migrate, restart (needs Git Bash)
rem    preuve backup       take a database backup now (needs Git Bash)
rem
rem  Add --no-browser to "preuve" or "preuve dev" to skip opening the browser.
rem  Starts Docker Desktop and Ollama first if they aren't running.
rem ============================================================================================
setlocal EnableExtensions EnableDelayedExpansion
rem Windows tools by full path: Git for Windows can put Unix tools of the same name first.

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PROD=docker compose -p preuve-prod --env-file "%ROOT%\infra\.env.prod" -f "%ROOT%\infra\docker-compose.prod.yml""
set "DEV=docker compose -p preuve --env-file "%ROOT%\.env" -f "%ROOT%\infra\docker-compose.yml""
set "BROWSER=1"
for %%A in (%*) do if /I "%%~A"=="--no-browser" set "BROWSER=0"

set "CMD=%~1"
if "%CMD%"=="" set "CMD=start"
if /I "%CMD%"=="--no-browser" set "CMD=start"

if /I "%CMD%"=="start"  goto :start_prod
if /I "%CMD%"=="dev"    goto :start_dev
if /I "%CMD%"=="stop"   goto :stop
if /I "%CMD%"=="status" goto :status
if /I "%CMD%"=="logs"   goto :logs
if /I "%CMD%"=="update" goto :update
if /I "%CMD%"=="backup" goto :backup
if /I "%CMD%"=="help"   goto :help
echo Unknown command "%CMD%".
goto :help

rem ------------------------------------------------------------------------------- production
:start_prod
if not exist "%ROOT%\infra\.env.prod" (
  echo infra\.env.prod is missing. Copy infra\.env.prod.example to infra\.env.prod and fill in
  echo POSTGRES_PASSWORD, OUTREACH_SECRET and SEARXNG_SECRET ^(see docs\operations.md^).
  exit /b 1
)
call :ensure_docker || exit /b 1
call :ensure_ollama
echo Starting Preuve...
%PROD% up -d --remove-orphans
if errorlevel 1 (
  echo Could not start the containers. If the images are missing, run: preuve update
  exit /b 1
)
echo Waiting for Preuve to be ready...
call :wait_url http://localhost:3100/api/health 90 || (
  echo Preuve didn't become healthy. Recent logs:
  %PROD% logs --tail 30 api web
  exit /b 1
)
echo.
echo   Preuve is running:  http://localhost:3100
echo   Stop it with:       preuve stop
if "%BROWSER%"=="1" start "" http://localhost:3100
exit /b 0

rem ------------------------------------------------------------------------------ development
:start_dev
if not exist "%ROOT%\.env" (
  echo .env is missing. Copy .env.example to .env first ^(see README.md^).
  exit /b 1
)
call :ensure_docker || exit /b 1
call :ensure_ollama
echo Starting the development databases and services...
%DEV% up -d postgres redis searxng mailpit greenmail || exit /b 1
call :wait_port 5435 60 || (echo Postgres didn't start. & exit /b 1)
echo Applying database migrations...
pushd "%ROOT%\apps\api"
uv run alembic upgrade head || (popd & exit /b 1)
popd
echo Opening the API, worker and web app in their own windows...
start "Preuve API (dev)" cmd /k "cd /d "%ROOT%\apps\api" && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
start "Preuve worker (dev)" cmd /k "cd /d "%ROOT%\apps\api" && uv run arq app.workers.settings.WorkerSettings"
start "Preuve web (dev)" cmd /k "cd /d "%ROOT%\apps\web" && pnpm dev"
echo Waiting for the web app...
call :wait_url http://localhost:3000/api/health 180 || (
  echo The dev app isn't answering yet; check the three windows for errors.
  exit /b 1
)
echo.
echo   Development app:  http://localhost:3000   (mail catcher: http://localhost:8025)
echo   Close the three windows to stop the app; "preuve stop dev" stops the containers.
if "%BROWSER%"=="1" start "" http://localhost:3000
exit /b 0

rem ------------------------------------------------------------------------------------- stop
:stop
echo Stopping Preuve...
if exist "%ROOT%\infra\.env.prod" %PROD% stop
if /I "%~2"=="dev" (
  echo Stopping the development containers...
  %DEV% stop
  echo Close the API, worker and web windows yourself if they're still open.
)
exit /b 0

rem ----------------------------------------------------------------------------------- status
:status
call :docker_up || (echo Docker isn't running. & exit /b 0)
echo == Preuve (production, http://localhost:3100)
if exist "%ROOT%\infra\.env.prod" (%PROD% ps --format "table {{.Service}}\t{{.Status}}") else (echo   not set up ^(no infra\.env.prod^))
echo.
echo == Development containers
%DEV% ps --format "table {{.Service}}\t{{.Status}}" 2>NUL
echo.
curl.exe -fsS -m 5 http://localhost:3100/api/health >NUL 2>&1 && (echo App health:  ok) || (echo App health:  not answering)
curl.exe -fsS -m 3 http://127.0.0.1:11434/api/tags >NUL 2>&1 && (echo Ollama:      running) || (echo Ollama:      not running)
exit /b 0

rem ------------------------------------------------------------------------------------- logs
:logs
%PROD% logs -f --tail 50 api worker web
exit /b 0

rem ---------------------------------------------------------------------- update and backup
:update
call :ensure_docker || exit /b 1
call :git_bash || exit /b 1
"%GITBASH%" "%ROOT%\infra\scripts\deploy.sh"
exit /b %errorlevel%

:backup
call :git_bash || exit /b 1
"%GITBASH%" "%ROOT%\infra\scripts\backup.sh"
exit /b %errorlevel%

:help
echo.
echo   preuve              start the app            http://localhost:3100
echo   preuve dev          start the development setup  http://localhost:3000
echo   preuve stop [dev]   stop it
echo   preuve status       what's running
echo   preuve logs         follow the logs
echo   preuve update       latest version + migrations
echo   preuve backup       database backup now
exit /b 0

rem ================================================================================= helpers
:docker_up
docker info >NUL 2>&1
exit /b %errorlevel%

:ensure_docker
call :docker_up && exit /b 0
set "DD=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
if not exist "%DD%" (
  echo Docker isn't running and Docker Desktop wasn't found. Start Docker, then try again.
  exit /b 1
)
echo Starting Docker Desktop ^(this can take a minute^)...
start "" "%DD%"
for /L %%i in (1,1,60) do (
  "%SystemRoot%\System32\timeout.exe" /t 3 /nobreak >NUL
  docker info >NUL 2>&1 && (echo Docker is ready. & exit /b 0)
)
echo Docker didn't start within 3 minutes.
exit /b 1

:ensure_ollama
curl.exe -fsS -m 3 http://127.0.0.1:11434/api/tags >NUL 2>&1 && exit /b 0
where ollama >NUL 2>&1 || (
  echo Note: Ollama isn't installed or running; the local model features won't work.
  exit /b 0
)
echo Starting Ollama...
start "Ollama" /min ollama serve
for /L %%i in (1,1,20) do (
  "%SystemRoot%\System32\timeout.exe" /t 1 /nobreak >NUL
  curl.exe -fsS -m 2 http://127.0.0.1:11434/api/tags >NUL 2>&1 && exit /b 0
)
echo Note: Ollama didn't answer yet; it may still be starting.
exit /b 0

:wait_url
rem  wait_url URL SECONDS
set /a "_tries=%~2/2"
for /L %%i in (1,1,%_tries%) do (
  curl.exe -fsS -m 3 -o NUL "%~1" >NUL 2>&1 && exit /b 0
  "%SystemRoot%\System32\timeout.exe" /t 2 /nobreak >NUL
)
exit /b 1

:wait_port
rem  wait_port PORT SECONDS  (a TCP port on 127.0.0.1 accepts connections)
set /a "_tries=%~2/2"
for /L %%i in (1,1,%_tries%) do (
  powershell -NoProfile -Command "try { (New-Object Net.Sockets.TcpClient('127.0.0.1', %~1)).Close(); exit 0 } catch { exit 1 }" >NUL 2>&1 && exit /b 0
  "%SystemRoot%\System32\timeout.exe" /t 2 /nobreak >NUL
)
exit /b 1

:git_bash
set "GITBASH=%ProgramFiles%\Git\bin\bash.exe"
if exist "%GITBASH%" exit /b 0
echo This needs Git Bash ^(Git for Windows^), which wasn't found at "%GITBASH%".
exit /b 1
