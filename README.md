# Laby AutoMute

Автомодерация чата HolyWorld: Python-бот + веб-панель + три LabyMod 4 аддона для Minecraft **1.20.1**.

- читает чат через моды (screenshotbridge, autologin, chatcopy)
- эвристики + LLM для детекта нарушений
- автомуты, скриншоты, загрузка на skr.sh
- dashboard на `http://127.0.0.1:9999` — правила, история, клиенты, API

## Структура

```
main.py              — точка входа
requirements.txt     — Python-зависимости
.env                 — конфиг (ключи, порты, пути)
moderator/           — бот, OCR, муты, Flask API
dashboard/           — React-панель (исходники)
addons/
  labymod-screenshot-addon/   — мост чата + скриншоты
  labymod-autologin-addon/    — автологин аккаунтов
  labymod-chatcopy-addon/     — кнопка [copy] в чате
scripts/
  build.sh           — полная сборка → dist.zip
  startser.bat       — стартер Windows
dist/                — результат build.sh (не в git)
```

## Требования

- **Python 3.10+**
- **JDK 21** (сборка аддонов)
- **Node.js 18+** (сборка dashboard)
- LabyMod 4, Minecraft 1.20.1

## Сборка

```bash
cd laby-automute
chmod +x scripts/build.sh
./scripts/build.sh
```

Скрипт собирает jar-моды, копирует Python-код, dashboard и `.env` в `dist/`, затем упаковывает `dist.zip`.

## Запуск (разработка)

```bash
pip install -r requirements.txt
cd dashboard && npm install && npm run build && cd ..
python main.py
```

Dashboard: http://127.0.0.1:9999  
Модерация по умолчанию **выключена** — включи во вкладке «Клиенты».

## Windows

Распакуй `dist.zip`, запусти `startser.bat`. Скрипт синхронизирует jar-моды в `C:\.minecraft\labymod-neo\addons\` и поднимает бота.

## Конфиг

| Файл | Назначение |
|------|------------|
| `.env` | API-ключи LLM, skr.sh, порты модов, пути к Minecraft (скопируй из `.env.example`) |
| `moderator/login_accounts.txt` | ник:пароль для автологина (скопируй из `login_accounts.txt.example`) |
| `moderator/staff_nicks.txt` | список ников персонала |

Данные рантайма (муты, правила, курсоры чата) пишутся в `%APPDATA%\mc-moderator\` на Windows.

## LabyMod аддоны

| Jar | Порт по умолчанию |
|-----|-------------------|
| screenshotbridge.jar | 47823 |
| autologin.jar | +100 к порту screenshot |
| chatcopy.jar | — |

Сборка отдельного аддона:

```bash
cd addons/labymod-screenshot-addon
./gradlew createReleaseJar
```
