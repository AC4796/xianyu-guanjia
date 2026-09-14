@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   闲鱼管家 - 一键启动
echo ========================================
echo.

python ensure_admin.py
if errorlevel 1 (
  echo [ERROR] 管理员初始化失败
  pause
  exit /b 1
)

echo.
echo [INFO] 地址: http://localhost:8080
echo [INFO] 账号: admin
echo [INFO] 密码: admin123
echo [INFO] 关闭本窗口会停止服务
echo.

start "" "http://localhost:8080/#/auth/login"
python Start.py

pause
