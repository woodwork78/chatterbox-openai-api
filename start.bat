@echo off
set HOST=%HOST%
if "%HOST%"=="" set HOST=0.0.0.0
set PORT=%PORT%
if "%PORT%"=="" set PORT=4123

uvicorn app.main:app --host %HOST% --port %PORT%
