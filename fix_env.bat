@echo off
echo 正在修复环境依赖问题...

echo 1. 卸载不兼容的包...
pip uninstall -y werkzeug flask

echo 2. 安装正确版本的依赖...
pip install werkzeug==2.0.1 -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
pip install flask==2.0.1 -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

echo 3. 环境修复完成，现在可以运行 python app.py 启动应用

pause 