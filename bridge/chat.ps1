# Talk to Vivian (demo settings: Gemini Flash-Lite, minimal thinking).
#   Local, Jabra on this PC:     powershell -ExecutionPolicy Bypass -File bridge\chat.ps1
#   From the Mac over UDP:       powershell -ExecutionPolicy Bypass -File bridge\chat.ps1 -Remote <MAC_IP>
#     on the Mac:  .venv/bin/python scripts/audio_send.py --host <PC_IP>                         (mic -> PC :50555)
#                  .venv/bin/python scripts/audio_recv.py --port 50556 --device "<Mac speakers>"  (Vivian's voice)
# Anything after the named parameters is passed through, e.g.  chat.ps1 -Remote 10.0.0.5 --monitor-delay 0.4
param([string]$Remote = "")
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$argList = @((Join-Path $PSScriptRoot "avatar_chat.py"), "--model", "gemini-flash-lite-latest", "--thinking", "minimal")
if ($Remote) { $argList += @("--remote", $Remote) }
& $py @argList @args
