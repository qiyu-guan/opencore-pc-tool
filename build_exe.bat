@echo off
echo 正在打包 OpenCore PC Tool...
pip install pyinstaller
pyinstaller --onefile --name opencore_pc_tool --console opencore_pc_tool.py
echo 打包完成！EXE 位于 dist\opencore_pc_tool.exe
pause
