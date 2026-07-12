import os
import uuid
from datetime import datetime

from .config import Settings
from .console import Console
from .deps import PIL_AVAILABLE
from .mod_client import ModScreenshotError, request_screenshot

if PIL_AVAILABLE:
    from PIL import Image

CHAT_CROP_WIDTH = 745


class ScreenshotService:
    def __init__(self, settings: Settings, console: Console):
        self.settings = settings
        self.console = console
        self.photos_dir = os.path.join(settings.base_dir, "photos")
        self.pending_dir = os.path.join(self.photos_dir, "pending")

    def capture(
        self,
        pending: bool = False,
        host: str | None = None,
        port: int | None = None,
    ) -> str | None:
        if not PIL_AVAILABLE:
            if self.settings.debug_upload:
                self.console.print("[DEBUG SCREENSHOT] PIL недоступен", self.console.yellow)
            return None

        out_dir = self.pending_dir if pending else self.photos_dir
        os.makedirs(out_dir, exist_ok=True)
        if pending:
            filename = f"pending-{uuid.uuid4().hex[:10]}.jpg"
        else:
            timestamp = datetime.now().strftime("%d-%m-%Y %H-%M-%S")
            filename = f"Скриншот-{timestamp}-{uuid.uuid4().hex[:6]}.jpg"
        filepath = os.path.join(out_dir, filename)

        try:
            if self.settings.debug_upload:
                self.console.print("[DEBUG SCREENSHOT] Запрос скриншота у мода...", self.console.yellow)

            response = request_screenshot(
                filepath,
                host=host or self.settings.mod_screenshot_host,
                port=port if port is not None else self.settings.mod_screenshot_port,
                timeout=5.0,
                fmt="jpg",
            )

            saved_path = response.get("path", filepath)
            if not os.path.isfile(saved_path):
                raise ModScreenshotError("file_not_created")

            width = int(response.get("width", 0))
            height = int(response.get("height", 0))
            cropped_path = self._crop_chat_region(saved_path, width, height)

            if self.settings.debug_upload:
                self.console.print(
                    f"[DEBUG SCREENSHOT] Скриншот сохранён: {cropped_path}",
                    self.console.green,
                )
            return cropped_path
        except ModScreenshotError as e:
            if self.settings.debug_upload:
                self.console.print(
                    f"[DEBUG SCREENSHOT] Мод недоступен: {e}",
                    self.console.red,
                )
            return None
        except Exception as e:
            if self.settings.debug_upload:
                self.console.print(
                    f"[DEBUG SCREENSHOT] Ошибка: {type(e).__name__}: {e}",
                    self.console.red,
                )
            return None

    def _crop_chat_region(self, path: str, width: int, height: int) -> str:
        if width <= 0 or height <= 0:
            with Image.open(path) as image:
                width, height = image.size

        left = 0
        top = int(height * 0.52)
        right = min(CHAT_CROP_WIDTH, width)
        bottom = height - 30

        if right <= left or bottom <= top:
            return path

        with Image.open(path) as image:
            cropped = image.crop((left, top, right, bottom))
            if cropped.mode != "RGB":
                cropped = cropped.convert("RGB")
            cropped.save(path, "JPEG")

        return path
