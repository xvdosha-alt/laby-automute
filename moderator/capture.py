import os
import sys

from .config import Settings
from .console import Console
from .screenshot import ScreenshotService


def main() -> int:
    settings = Settings.load()
    console = Console()
    screenshot = ScreenshotService(settings, console)

    path = screenshot.capture()
    if not path:
        console.print(
            "Не удалось сделать скриншот. Запусти Minecraft Fabric 1.20.1 с модом screenshot-bridge.",
            console.red,
        )
        return 1

    console.print(f"Скриншот: {path}", console.green)

    if sys.platform == "win32":
        os.startfile(path)
    else:
        console.print("Автооткрытие доступно только на Windows.", console.yellow)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
