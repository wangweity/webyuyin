@echo off
echo 准备启动网页朗读助手...

echo 1. 安装 wheel 包...
pip install wheel -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

echo 2. 安装其他依赖...
pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

echo 3. 启动应用...
python app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo 应用启动失败，请检查上面的错误信息。
    echo 如果是 lxml 包安装问题，您可以尝试手动安装预编译的 wheel：
    echo pip install lxml --only-binary=:all: -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
    echo.
)

pause 