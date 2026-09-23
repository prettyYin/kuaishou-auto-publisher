@echo off
chcp 65001 >nul
pushd "%~dp0"
setlocal
set "LOGFILE=%~dp0启动日志.txt"
echo ===== 准备浏览器配置 %date% %time% ===== >> "%LOGFILE%"

set "PYEXE="
set "PYARGS="
if exist "F:\MySofeware\dev_tools\Python\Python39\python.exe" set "PYEXE=F:\MySofeware\dev_tools\Python\Python39\python.exe"
if not defined PYEXE (
  where python >nul 2>nul
  if not errorlevel 1 for /f "delims=" %%i in ('where python') do if not defined PYEXE set "PYEXE=%%i"
)
if not defined PYEXE (
  where py >nul 2>nul
  if not errorlevel 1 (
    for /f "delims=" %%i in ('where py') do if not defined PYEXE set "PYEXE=%%i"
    set "PYARGS=-3"
  )
)
if not defined PYEXE (
  echo.
  echo 没有找到 Python，无法启动。请先安装 Python 或联系助手。
  echo 没有找到 Python >> "%LOGFILE%"
  echo.
  pause
  popd
  exit /b 1
)
echo 使用解释器：%PYEXE% %PYARGS% >> "%LOGFILE%"

echo 准备自动化专用的浏览器配置（保留登录态，不影响日常使用）
"%PYEXE%" %PYARGS% -X utf8 -m app.prepare_profiles
set "RC=%ERRORLEVEL%"
echo 退出码：%RC% >> "%LOGFILE%"
if not "%RC%"=="0" (
  echo.
  echo 执行失败（代码 %RC%）。请把工具目录里的「启动日志.txt」发给助手。
  echo.
  pause
)
popd
endlocal
