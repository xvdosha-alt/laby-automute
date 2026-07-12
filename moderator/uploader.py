import os
import time

from .config import Settings
from .console import Console
from .deps import REQUESTS_AVAILABLE, http_session, requests
from .skrsh_api import (
    build_screenshot_id,
    build_short_url,
    build_upload_filename,
    encode_filename,
    make_app_id,
)


class ImageUploader:
    def __init__(self, settings: Settings, console: Console):
        self.settings = settings
        self.console = console
        self._free_ids: list[str] = []

    def _debug(self, message: str, color: str | None = None) -> None:
        if self.settings.debug_upload:
            self.console.print(message, color or self.console.yellow)

    def _get_app_id(self) -> str:
        if self.settings.skr_app_id:
            return self.settings.skr_app_id

        app_id_path = os.path.join(self.settings.base_dir, "skr_app_id.txt")
        if os.path.isfile(app_id_path):
            with open(app_id_path, encoding="utf-8") as f:
                stored = f.read().strip()
            if stored:
                return stored

        app_id = make_app_id()
        with open(app_id_path, "w", encoding="utf-8") as f:
            f.write(app_id)
        return app_id

    def _fetch_free_ids(self) -> bool:
        try:
            response = http_session().get(self.settings.skr_uids_url, timeout=30)
            if response.status_code != 200:
                self._debug(f"[DEBUG UPLOAD] uids HTTP {response.status_code}", self.console.red)
                return False

            data = response.json()
            if data.get("status") != "ok":
                self._debug(f"[DEBUG UPLOAD] uids status: {data}", self.console.red)
                return False

            uids = data.get("uids") or []
            if not uids:
                self._debug("[DEBUG UPLOAD] uids пустой", self.console.red)
                return False

            self._free_ids.extend(uids)
            return True
        except Exception as e:
            self._debug(f"[DEBUG UPLOAD] uids ошибка: {type(e).__name__}: {e}", self.console.red)
            return False

    def _take_free_id(self) -> str | None:
        if not self._free_ids and not self._fetch_free_ids():
            return None
        if not self._free_ids:
            return None
        return self._free_ids.pop()

    def _file_ext(self, path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        if ext in (".jpg", ".jpeg"):
            return ".jpg"
        if ext == ".png":
            return ".png"
        return ".jpg"

    def upload(self, path: str, nickname: str | None = None) -> str | None:
        if not REQUESTS_AVAILABLE:
            return None

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            free_id = self._take_free_id()
            if not free_id:
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return None

            try:
                app_id = self._get_app_id()
                file_ext = self._file_ext(path)
                screenshot_id = build_screenshot_id(free_id)
                file_name = build_upload_filename()
                if nickname:
                    file_name = f"{nickname} {file_name}"

                self._debug(
                    f"[DEBUG UPLOAD] Попытка {attempt}/{max_retries}: "
                    f"freeId={free_id}, screenshotId={screenshot_id}",
                )

                with open(path, "rb") as f:
                    response = http_session().post(
                        self.settings.skr_upload_url,
                        data={
                            "appId": app_id,
                            "screenshotId": screenshot_id,
                            "fileExt": file_ext,
                            "uploadType": "0",
                            "fileName": encode_filename(file_name),
                        },
                        files={
                            "userfile": (
                                os.path.basename(path),
                                f,
                                "image/jpeg" if file_ext == ".jpg" else "image/png",
                            )
                        },
                        timeout=(30, 60),
                    )

                self._debug(f"[DEBUG UPLOAD] Статус ответа: {response.status_code}")

                if response.status_code != 200:
                    self._debug(
                        f"[DEBUG UPLOAD] HTTP ошибка {response.status_code}: {response.text[:200]}",
                        self.console.red,
                    )
                    if attempt < max_retries:
                        time.sleep(2)
                        continue
                    return None

                try:
                    result = response.json()
                except ValueError as e:
                    self._debug(
                        f"[DEBUG UPLOAD] Ошибка парсинга JSON: {e}. Ответ: {response.text[:200]}",
                        self.console.red,
                    )
                    return None

                self._debug(f"[DEBUG UPLOAD] Ответ API: {result}")

                if result.get("status") == 0:
                    url = build_short_url(free_id, self.settings.skr_short_base)
                    self._debug(f"[DEBUG UPLOAD] Ссылка: {url}", self.console.green)
                    return url

                self._debug(f"[DEBUG UPLOAD] Ошибка API status={result.get('status')}", self.console.red)
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return None

            except requests.exceptions.ConnectionError as e:
                self._debug(
                    f"[DEBUG UPLOAD] Ошибка соединения ({attempt}/{max_retries}): {e}",
                    self.console.red,
                )
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return None
            except requests.exceptions.Timeout:
                self._debug(
                    f"[DEBUG UPLOAD] Таймаут ({attempt}/{max_retries}), повторяю...",
                    self.console.red,
                )
                if attempt < max_retries:
                    continue
                return None
            except Exception as e:
                self._debug(
                    f"[DEBUG UPLOAD] Исключение ({attempt}/{max_retries}): {type(e).__name__}: {e}",
                    self.console.red,
                )
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return None

        return None
