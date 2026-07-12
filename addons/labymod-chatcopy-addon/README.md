# Chat Copy (LabyMod 4)

Addon для Minecraft 1.20.1: кнопка `[copy]` после каждого сообщения в чате.

## Сборка

Требуется **JDK 21**.

```bash
./build.sh
```

Windows:

```bat
build.bat
```

Jar: `dist/chatcopy.jar` → `C:\.minecraft\labymod-neo\addons\`

## Структура

| Модуль | Назначение |
|--------|------------|
| `core/` | Слушатели чата, кнопка copy, отключение fade |
| `game-runner/` | LabyMod 1.20.1 runtime |

## Исходники

- `ChatCopyListener` — вешает `[copy]` на сообщения
- `ChatCopySuffix` — clipboard + форматирование
- `ChatAnimationDisabler` / `ChatFadeGuard` — чат без анимации fade
