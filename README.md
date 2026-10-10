# dt: talking MetaHuman (hackathon)

Speak into a mic and a UE 5.8 MetaHuman (preset "Vivian") answers out loud, lip-synced by Epic's MetaHuman (Audio) Live Link source, with a mood picked by the LLM.

| Folder | What | Start here |
|---|---|---|
| `unreal-integration/` | UE 5.8 project setup, MetaHuman, Audio Live Link, MCP/PyJobs tooling, measurements | `WINDOWS_HANDOFF.md`, `test_results.md` |
| `bridge/` | Voice loop: mic → Gradium STT → Gemini → Gradium TTS → virtual cable → face | `bridge/README.md` |

Demo on the Windows PC:

```powershell
powershell -ExecutionPolicy Bypass -File unreal-integration\scripts\launch_editor.ps1   # wait for the editor, open L_AudioTest
bridge\.venv\Scripts\python bridge\avatar_chat.py --model gemini-flash-lite-latest --thinking minimal
```

Keys live in `.env` (gitignored; see `.env.example`).
