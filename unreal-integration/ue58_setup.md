# UE 5.8 install (Epic Games Launcher)

**Status:** the launcher started downloading at 11:25 on 2026-10-10 into `/Users/Shared/Epic Games/UE_5.8`.

## Launcher steps

1. Open **Epic Games Launcher → Unreal Engine → Library**.
2. Next to the Engine Versions **+**, choose **5.8.x → Install**. Location: `/Users/Shared/Epic Games` (the default).
3. Click **Options** before or during install and make sure these are ticked:
   - **Core Components** (required)
   - **MetaHuman Creator Core Data** (required for creating or assembling MetaHumans in-editor)
   - Starter Content and Templates (optional, small)
   - Leave **Editor symbols for debugging** off (tens of GB) and target platforms (iOS, Android, Linux) off unless needed.
4. After installing, click **Launch** once so the launcher registers the engine and finishes first-run setup.

If the install already started without Core Data: when it finishes, go to **Library → 5.8 ▾ → Options**, tick **MetaHuman Creator Core Data** and click **Apply**. It downloads incrementally.

## Verification (run after install)

```bash
cat "/Users/Shared/Epic Games/UE_5.8/Engine/Build/Build.version"
find "/Users/Shared/Epic Games/UE_5.8/Engine/Plugins" -iname "*MetaHuman*.uplugin"
```

The results go in `test_results.md`.

## Project

Created by `scripts/create_project.sh` at:

```
~/Documents/Unreal Projects/GradiumMH/GradiumMH.uproject
```

It lives outside the git repo on purpose, because MetaHuman assets and DerivedDataCache run to many GB. Only scripts and docs are in git.
