import sys

from .deps import COLORAMA_AVAILABLE, Fore, Style


class Console:
    def __init__(self, runtime_state=None):
        self._runtime = runtime_state

    def print(self, text: str, color: str = "") -> None:
        try:
            encoding = sys.stdout.encoding or "utf-8"
        except Exception:
            encoding = "utf-8"

        if COLORAMA_AVAILABLE and color:
            text = f"{color}{text}{Style.RESET_ALL}"

        data = (text + "\n").encode(encoding, errors="replace")
        try:
            sys.stdout.buffer.write(data)
            sys.stdout.flush()
        except Exception:
            try:
                sys.stdout.write(
                    (text + "\n").encode(encoding, errors="replace").decode(
                        encoding, errors="replace"
                    )
                )
                sys.stdout.flush()
            except Exception:
                pass

        if self._runtime is not None:
            self._runtime.add_log(text, self._level_for_color(color))

    @staticmethod
    def _level_for_color(color: str) -> str:
        if COLORAMA_AVAILABLE:
            if color == Fore.GREEN:
                return "green"
            if color == Fore.YELLOW:
                return "yellow"
            if color == Fore.RED:
                return "red"
            if color == Fore.MAGENTA:
                return "purple"
        return "default"

    @property
    def green(self):
        return Fore.GREEN if COLORAMA_AVAILABLE else ""

    @property
    def yellow(self):
        return Fore.YELLOW if COLORAMA_AVAILABLE else ""

    @property
    def red(self):
        return Fore.RED if COLORAMA_AVAILABLE else ""

    @property
    def purple(self):
        return Fore.MAGENTA if COLORAMA_AVAILABLE else ""
