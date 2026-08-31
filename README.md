EN | [RU](docs/README_RU.md)

## Laby AutoMute 🔇

HolyWorld chat auto-moderation: Python bot + web panel + three LabyMod 4 addons for Minecraft **1.20.1**.

- reads chat via mods (screenshotbridge, autologin, chatcopy)
- heuristics + LLM for violation detection
- auto-mutes, screenshots, upload to skr.sh
- dashboard at `http://127.0.0.1:9999` - rules, history, clients, API

## Structure

```
main.py              - entry point
requirements.txt     - Python dependencies
.env                 - config (keys, ports, paths)
moderator/           - bot, OCR, mutes, Flask API
dashboard/           - React panel (sources)
addons/
  labymod-screenshot-addon/   - chat bridge + screenshots
  labymod-autologin-addon/    - account auto-login
  labymod-chatcopy-addon/     - [copy] button in chat
scripts/
  build.sh           - full build → dist.zip
  startser.bat       - Windows starter
dist/                - build.sh output (not in git)
```

## Requirements

- **Python 3.10+**
- **JDK 21** (addon build)
- **Node.js 18+** (dashboard build)
- LabyMod 4, Minecraft 1.20.1

## Build

```bash
cd laby-automute
chmod +x scripts/build.sh
./scripts/build.sh
```

The script builds jar mods, copies Python code, dashboard and `.env` into `dist/`, then packs `dist.zip`.

## 🚀 Quick start (development)

```bash
pip install -r requirements.txt
cd dashboard && npm install && npm run build && cd ..
python main.py
```

Dashboard: http://127.0.0.1:9999
Moderation is **off** by default - enable it in the Clients tab.

## Windows

Unpack `dist.zip`, run `startser.bat`. The script syncs jar mods to `C:\.minecraft\labymod-neo\addons\` and starts the bot.

## ⚙️ Configuration

| File | Purpose |
|------|---------|
| `.env` | LLM API keys, skr.sh, mod ports, Minecraft paths (copy from `.env.example`) |
| `moderator/login_accounts.txt` | nick:password for auto-login (copy from `login_accounts.txt.example`) |
| `moderator/staff_nicks.txt` | staff nick list |

Runtime data (mutes, rules, chat cursors) is written to `%APPDATA%\mc-moderator\` on Windows.

## LabyMod addons

| Jar | Default port |
|-----|--------------|
| screenshotbridge.jar | 47823 |
| autologin.jar | +100 to screenshot port |
| chatcopy.jar | - |

Build a single addon:

```bash
cd addons/labymod-screenshot-addon
./gradlew createReleaseJar
```
