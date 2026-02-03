@echo off
REM SmartInput 构建脚本
REM 用于将 main.py 打包成 SmartInput.exe

echo.
echo ========================================
echo SmartInput 打包脚本
echo ========================================
echo.

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python
    echo 请安装 Python 3.7 或更高版本
    pause
    exit /b 1
)

echo [步骤 1] 检查虚拟环境...
if not exist ".venv" (
    echo 创建虚拟环境...
    python -m venv .venv
) else (
    echo 虚拟环境已存在
)

echo.
echo [步骤 2] 激活虚拟环境并安装依赖...
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
if errorlevel 1 (
    echo 错误: 安装依赖失败
    pause
    exit /b 1
)

echo.
echo [步骤 3] 运行 PyInstaller...
python -m PyInstaller SmartInput.spec --distpath dist
if errorlevel 1 (
    echo 错误: PyInstaller 打包失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo 打包完成！
echo ========================================
echo.
echo 可执行文件位置: dist\SmartInput.exe
echo.
echo 您可以:
echo 1. 直接运行: dist\SmartInput.exe
echo 2. 创建快捷方式到桌面
echo 3. 添加到 Windows 启动文件夹（开机自启）
echo.
pause
