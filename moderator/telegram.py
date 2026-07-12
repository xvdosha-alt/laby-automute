from .config import Settings
from .console import Console


class TelegramNotifier:
    def __init__(self, settings: Settings, console: Console | None = None):
        self.settings = settings
        self.console = console

    def send_photo(self, photo_path: str, caption: str) -> bool:
        return False
