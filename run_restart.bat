@echo off
echo 准备启动网页朗读助手（修复版）...

REM 确保使用正确的依赖版本
echo 安装兼容的依赖版本...
pip install werkzeug==2.0.1 flask==2.0.1 -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
pip install requests==2.26.0 beautifulsoup4==4.10.0 lxml -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

echo 启动应用...
python app.py

pause 