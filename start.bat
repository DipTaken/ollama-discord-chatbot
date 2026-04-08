@echo off
echo Starting Ollama Discord Bot...

echo Starting Ollama model...
start ollama serve
timeout /t 2 /nobreak > nul

echo Starting Discord bot...
python main.py
pause
