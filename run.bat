@echo off
title DrillAI Runner
cd /d "F:\drill-ai"
start powershell.exe -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath 'F:\drill-ai'; python main.py start"
