from .config import Settings
from .console import Console
from .models import ChatMessage


class PhotoAnnotator:
    def __init__(self, settings: Settings, console: Console):
        self.settings = settings
        self.console = console

    def highlight(
        self,
        photo_path: str,
        messages: list[ChatMessage],
        focus_nick: str | None = None,
    ) -> bool:
        return False
