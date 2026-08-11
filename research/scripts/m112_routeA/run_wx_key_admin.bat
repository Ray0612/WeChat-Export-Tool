@echo off
echo 请求管理员权限...
powershell -Command "Start-Process python -ArgumentList 'C:\Users\OK\Desktop\use_wx_key.py' -Verb RunAs -Wait"
pause
