import re
import time

from .config import Settings
from .console import Console
from .deps import REQUESTS_AVAILABLE, http_session, requests
from .chat_filters import looks_like_begging, looks_like_trade_ad
from .heuristics import HeuristicChecker
from .models import ChatMessage
from .prompt import SYSTEM_PROMPT
from .rules_config import KNOWN_RULE_IDS, ML_ALLOWED_RULE_IDS, RulesConfig

MANUAL_ONLY_RULES = frozenset({"2.3", "3.12"})


class LLMClient:
    _quota_blocked_until: float = 0.0
    _model_blocked_until: dict[str, float] = {}

    def __init__(self, settings: Settings, console: Console):
        self.settings = settings
        self.console = console
        self.last_error: str = ""

    def _debug(self, message: str) -> None:
        if self.settings.debug_ml:
            self.console.print(message, self.console.yellow)

    def _request_completion(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        key_idx: int,
        api_key: str,
        max_retries: int,
        retryable_status: set[int],
    ) -> tuple[str | None, bool]:
        for attempt in range(1, max_retries + 1):
            try:
                self._debug(
                    f"[DEBUG ML] Попытка {key_idx}/{len(self.settings.llm_api_keys)} "
                    f"({attempt}/{max_retries}) model={model}..."
                )
                self._debug(
                    f"[DEBUG ML] POST {self.settings.llm_api_url} model={model}"
                )

                payload: dict = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": self.settings.ml_temperature,
                    "max_tokens": max_tokens,
                }
                if system_prompt:
                    payload["system"] = system_prompt

                response = http_session().post(
                    url=self.settings.llm_api_url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=(15, self.settings.ml_api_timeout),
                )

                self._debug(f"[DEBUG ML] Статус ответа: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()
                    if "error" in result:
                        self._debug(
                            "[DEBUG ML] Ошибка в ответе API: "
                            f"{result.get('error', {}).get('message', 'Unknown error')[:200]}"
                        )
                        break

                    choices = result.get("choices") or []
                    if choices:
                        content = choices[0].get("message", {}).get("content")
                        if content:
                            return content.strip(), False

                    self._debug("[DEBUG ML] Пустой или неожиданный ответ")
                    break

                self._debug(f"[DEBUG ML] Ошибка HTTP: {response.status_code}")
                self.last_error = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown error")
                    self.last_error = error_msg
                    self._debug(f"[DEBUG ML] Сообщение об ошибке: {error_msg}")
                except Exception as parse_error:
                    self._debug(f"[DEBUG ML] Не удалось распарсить JSON: {parse_error}")
                    error_msg = ""

                no_channel = "no available channel" in (error_msg or response.text).lower()
                if no_channel:
                    cooldown = max(30.0, self.settings.ml_quota_cooldown / 2)
                    LLMClient._model_blocked_until[model] = time.monotonic() + cooldown
                    self._debug(
                        f"[DEBUG ML] Модель {model} недоступна на Clodex, "
                        f"пропуск на {int(cooldown)} сек"
                    )
                    return None, True

                if response.status_code == 401:
                    break

                plan_limit = response.status_code == 429 and (
                    "plan limit" in (error_msg or response.text).lower()
                    or "套餐" in (error_msg or response.text)
                )
                if plan_limit:
                    cooldown = max(60.0, self.settings.ml_quota_cooldown)
                    LLMClient._quota_blocked_until = time.monotonic() + cooldown
                    self._debug(
                        f"[DEBUG ML] Квота API исчерпана, пауза {int(cooldown)} сек"
                    )
                    break

                if response.status_code in retryable_status and attempt < max_retries:
                    self._debug("[DEBUG ML] Повтор через 2 сек...")
                    time.sleep(2)
                    continue

                body_preview = response.text[:200].replace("\n", " ")
                self._debug(f"[DEBUG ML] Ответ: {body_preview}")
                break

            except requests.exceptions.Timeout as e:
                self._debug(f"[DEBUG ML] Таймаут ({self.settings.ml_api_timeout}с): {e}")
                if attempt < max_retries:
                    self._debug("[DEBUG ML] Повтор через 2 сек...")
                    time.sleep(2)
                    continue
                break
            except Exception as e:
                self._debug(f"[DEBUG ML] Исключение при запросе: {e}")
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                break

        return None, False

    def _chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
    ) -> str | None:
        if not REQUESTS_AVAILABLE:
            return None

        api_keys = self.settings.llm_api_keys
        if not api_keys:
            return None

        blocked_for = LLMClient._quota_blocked_until - time.monotonic()
        if blocked_for > 0:
            self.last_error = f"quota cooldown {int(blocked_for)}s"
            self._debug(
                f"[DEBUG ML] Квота API: пропуск запроса ({int(blocked_for)} сек)"
            )
            return None

        max_retries = 3
        retryable_status = {429, 502, 503, 504, 520}
        tokens = max_tokens if max_tokens is not None else self.settings.ml_max_tokens

        now = time.monotonic()
        for model in self.settings.llm_models:
            blocked_for = LLMClient._model_blocked_until.get(model, 0.0) - now
            if blocked_for > 0:
                self._debug(
                    f"[DEBUG ML] Модель {model} в паузе ({int(blocked_for)} сек), пропуск"
                )
                continue

            for key_idx, api_key in enumerate(api_keys, 1):
                answer, model_unavailable = self._request_completion(
                    model,
                    system_prompt,
                    user_prompt,
                    tokens,
                    key_idx,
                    api_key,
                    max_retries,
                    retryable_status,
                )
                if model_unavailable:
                    break
                if answer is not None:
                    return answer

        return None

    def check_batch(self, messages: list[ChatMessage]) -> str | None:
        if not REQUESTS_AVAILABLE:
            self._debug("[DEBUG ML] requests недоступен")
            return None

        if not messages:
            self._debug("[DEBUG ML] Пустой батч")
            return None

        blocked_for = LLMClient._quota_blocked_until - time.monotonic()
        if blocked_for > 0:
            self.last_error = f"quota cooldown {int(blocked_for)}s"
            self._debug(
                f"[DEBUG ML] Квота API: пропуск батча ({int(blocked_for)} сек)"
            )
            return None

        api_keys = self.settings.llm_api_keys
        for i, key in enumerate(api_keys, 1):
            self._debug(f"[DEBUG ML] Найден ключ {i}: {key[:20]}...")

        self._debug(f"[DEBUG ML] Всего найдено ключей: {len(api_keys)}")
        if not api_keys:
            self._debug("[DEBUG ML] Нет доступных API ключей")
            return None

        batch = messages[-self.settings.ml_batch_size :]
        messages_text = "\n".join(
            msg.format_batch_line(i) for i, msg in enumerate(batch, 1)
        )
        user_prompt = (
            f"Сообщения для проверки:\n{messages_text.strip()}\n\n"
            "Ответь строго одной строкой без анализа: none или /tempmute ник время правило "
            "(обязательно пробел между временем и правилом: 3h 3.4, не 3h3.4). "
            "Время строго: 3.4=3h, 3.6=7h, 3.7=3h, 3.8=2h, 3.9=9h, 3.10=5h. "
            "Никогда не используй 1h."
        )

        self._debug("[DEBUG ML] Отправка запроса в нейронку...")
        self._debug(
            f"[DEBUG ML] Порядок моделей: {', '.join(self.settings.llm_models)}"
        )
        for msg in batch:
            self._debug(f"[DEBUG ML]   [{msg.timestamp}] {msg.nickname}: {msg.text}")

        self.last_error = ""
        answer = self._chat_completion(SYSTEM_PROMPT, user_prompt)
        if answer is not None:
            self._debug(f"[DEBUG ML] Ответ нейронки: {answer}")
            return answer

        self._debug("[DEBUG ML] Все модели и ключи исчерпаны, продолжаем без нейронки")
        return None

    @staticmethod
    def extract_mute_command(result: str) -> str | None:
        match = re.search(
            r"/tempmute\s+\S+\s+\S+\s+\S+",
            result,
            re.IGNORECASE,
        )
        if match:
            return match.group(0).strip()
        for line in result.split("\n"):
            if line.lower().strip().startswith("/tempmute"):
                return line.strip()
        return None

    _FAMILY_MARKERS = (
        "мать",
        "матер",
        "мамк",
        "мамаш",
        "маму",
        "маме",
        "мама",
        "безмам",
        "отец",
        "отца",
        "отцу",
        "отчим",
        "папк",
        "папу",
        "папе",
        "папа",
        "батя",
        "сын",
        "сына",
        "дочь",
        "дочер",
        "дед",
        "деда",
        "бабуш",
        "бабул",
        "родител",
        "родн",
        "mq",
    )

    _STRONG_INSULT_MARKERS = (
        "лох",
        "лошар",
        "дебил",
        "даун",
        "мудак",
        "мудил",
        "чмо",
        "уёб",
        "уеб",
        "пидор",
        "пидр",
        "шлюх",
        "шалав",
        "ебан",
        "ёбан",
        "ебал",
        "ёбал",
        "сука",
        "бляд",
        "хуй",
        "хуе",
        "пизд",
        "мраз",
        "урод",
        "твар",
        "гандон",
        "петух",
        "член",
        "соси",
        "сосал",
        "долбо",
        "конч",
        "нищ",
        "шавк",
        "шмар",
        "падл",
        "ублюд",
        "выбляд",
    )

    _WEAK_34_WORDS = frozenset({
        "бот", "беспомощный", "нулина", "школьник", "детсадовец", "нуб", "рак",
        "пипдастр", "нытик", "плакса", "оболтус", "слабый", "кабачок", "кринж",
        "ez", "ezka", "лёгкий", "легкий", "анскил", "слитый", "пакостник",
        "стукач", "шулер", "алкаш", "барыга", "людоед", "задрот", "ущербный",
        "похуист", "трус", "эгоист", "неудачник", "ахуевший", "мямля", "бредкий",
        "трутень", "нахал", "пижон", "шмакодявка", "изверг", "qq", "q",
        "тупой", "тупица", "лошара", "лошар", "otebiz", "отъебись", "отвали",
        "завали", "понял", "слишком", "просто", "чтобы", "понять",
        "мм", "xd", "хз", "норм", "неплохо", "уфффф", "уфф", "л",
    })

    _DURATION_RULE_RE = re.compile(r"^(\d+h)\s*(\d+\.\d+)$", re.IGNORECASE)

    _CHAT_GAME_37_MARKERS = (
        "комму топку",
        "кому топку",
        "топку +",
        "топку+",
        "плюс в чат",
        "+ в чат",
        "кто +",
        "кто перебь",
        "кто первый",
    )

    _GIVEAWAY_37_MARKERS = (
        "конкурс",
        "розыгрыш",
        "главный приз",
        "приз ",
        "уник",
        "2кк",
        "раздам",
        "дам коин",
        "тому 2к",
        "кто выберет",
        "тепаю на",
        "тпаю на",
        "топаю на",
        "телепорт на",
        "откуп",
    )

    _STRONG_SEXUAL_MARKERS = (
        "хуй",
        "хуе",
        "хуя",
        "пизд",
        "член",
        "жоп",
        "соси",
        "сосал",
        "сосать",
        "минет",
        "трах",
        "анал",
        "конч",
        "эрек",
        "оргаз",
        "порно",
        "выеб",
        "ебу теб",
        "ебать теб",
    )

    _WEAK_SEXUAL_WORDS = (
        "рабын",
        "проститут",
        "шлюх",
        "сексу",
        "облизы",
        "оближ",
    )

    _GAME_HOLE_RE = re.compile(
        r"(?:\b\d+\s+|\bв\s+\d+\s+)дырк",
        re.IGNORECASE,
    )

    _SERIOUS_39_MARKERS = (
        "нацист",
        "нацизм",
        "гитлер",
        "свастик",
        "zigger",
        "ниггер",
        "террор",
        "теракт",
        "суицид",
        "повешусь",
        "повешение",
        "наркот",
        "героин",
        "кокаин",
        "метамф",
        "спайс",
        "марихуан",
        "взорву",
        "бомбу залож",
        "в реале",
        "в жизни",
        "найду домой",
        "адрес знаю",
        "порежу себ",
        "режу себ",
        "расист",
        "ксенофоб",
        "фашист",
    )

    _INGAME_39_CONTEXT_MARKERS = (
        "трап",
        "пвп",
        "pvp",
        "сет",
        "крист",
        "крип",
        "инв",
        "килл",
        "kill",
        "фулл",
        "донат",
        "спавн",
        "фарм",
        "драг",
        "элитр",
        "перл",
        "чар",
        "уник",
        "дракон",
        "ивент",
    )

    _KILL_VERB_39_RE = re.compile(
        r"\b(?:"
        r"уби\w*|"
        r"зареж\w*|"
        r"пристрел\w*|"
        r"закил\w*|"
        r"кильн\w*"
        r")\b",
        re.IGNORECASE,
    )

    @staticmethod
    def _is_ingame_kill_talk(text: str) -> bool:
        lowered = text.lower()
        if any(marker in lowered for marker in LLMClient._SERIOUS_39_MARKERS):
            return False
        if not LLMClient._KILL_VERB_39_RE.search(lowered):
            return False
        if any(marker in lowered for marker in LLMClient._INGAME_39_CONTEXT_MARKERS):
            return True
        if re.search(r"хот\w*\s+уби", lowered):
            return True
        if re.search(r"когда\s+\w+\s+убь", lowered):
            return True
        if re.search(
            r"(?:"
            r"попробуй\w*\s+(?:\w+\s+){0,3}(?:кого-то\s+)?уби"
            r"|(?:убь|уби)\w*\s+(?:тебя|вас|вам|тебе|всех)"
            r"|(?:тебя|вас|вам|тебе|всех)\s+(?:\w+\s+){0,4}(?:убь|уби)"
            r")",
            lowered,
        ):
            return True
        if re.search(r"\b(?:он|она|они)\s+уби", lowered):
            return True
        if (
            re.search(r"\bне\s+вер\w*", lowered)
            and LLMClient._KILL_VERB_39_RE.search(lowered)
        ):
            return True
        return False

    @staticmethod
    def _looks_like_strong_insult(text: str) -> bool:
        if LLMClient._is_mild_34_message(text):
            return False
        return HeuristicChecker.has_explicit_insult(text)

    @staticmethod
    def _is_mild_34_message(text: str) -> bool:
        lowered = text.lower().strip()
        if HeuristicChecker.is_self_directed_insult(text):
            return True
        compact = re.sub(r"[^a-zа-яё0-9]+", "", lowered)
        if compact in {"otebiz", "отъебись", "отвали", "завали", "завались"}:
            return True
        if re.fullmatch(r"(соси|понял|xd|мм|л|уфф+)", compact):
            return True
        if re.search(r"\bнахуй\s+ты\b", lowered) and not re.search(
            r"\b(иди|пош[её]л|съеби|съебись|нахуй\s+иди|иди\s+нахуй)\b", lowered
        ):
            return True
        if re.search(r"\bслишком\s+туп", lowered) and not any(
            marker in lowered for marker in ("ебан", "ёбан", "пидор", "мраз", "уёб", "уеб")
        ):
            return True
        if HeuristicChecker.has_gibberish_spam(text) and re.search(r"\bнахуй\b", lowered):
            return True
        if re.search(r"^[0-9]+[xх×]\d*\b", lowered) and HeuristicChecker.has_gibberish_spam(text):
            return True
        return False

    @staticmethod
    def is_manual_only_reason(reason: str) -> bool:
        rule = (reason or "").strip()
        return any(rule.startswith(prefix) for prefix in MANUAL_ONLY_RULES)

    @staticmethod
    def _looks_like_mute_dispute(text: str) -> bool:
        lowered = text.lower()
        markers = (
            "не согласен с мут",
            "не согласна с мут",
            "не согласен с бан",
            "не согласна с бан",
            "я не согласен",
            "я не согласна",
            "я не виноват",
            "я не виновата",
            "зря мут",
            "зря бан",
            "зря замут",
            "зря забан",
        )
        if any(marker in lowered for marker in markers):
            return True
        stripped = re.sub(r"https?://\S+|//skr\.sh/\S+", "", lowered).strip()
        if stripped and re.search(r"\bне\s+соглас", stripped):
            return True
        if stripped and re.search(r"\bне\s+виноват", stripped):
            return True
        return False

    @staticmethod
    def _looks_like_trade_ad(text: str) -> bool:
        return looks_like_trade_ad(text)

    @staticmethod
    def _looks_like_punishment_interference(text: str) -> bool:
        lowered = text.lower()
        markers = (
            "за что мут",
            "за что бан",
            "за что забан",
            "за что замут",
            "неверно забан",
            "неверно замут",
            "неправильно забан",
            "неправильно замут",
            "не за что бан",
            "не за что мут",
            "обжаловать",
            "обжалую",
            "зря забан",
            "зря замут",
            "зря выдал",
            "зря дал мут",
            "зря дал бан",
            "отмените бан",
            "отмените мут",
            "сними мут",
            "сними бан",
            "разбань",
            "размуть",
            "размути",
        )
        if any(marker in lowered for marker in markers):
            return True
        if re.search(r"\b(?:забанен|замучен|забанили|замутили)\b", lowered):
            if re.search(r"\b(?:неверно|неправильно|зря|не\s+за)\b", lowered):
                return True
        return False

    @staticmethod
    def parse_mute_command_fields(command: str) -> tuple[str, str, str] | None:
        parts = command.split()
        if len(parts) < 3 or not parts[0].lower().startswith("/tempmute"):
            return None
        nickname = parts[1]
        duration = parts[2]
        rule = parts[3] if len(parts) > 3 else ""
        merged = LLMClient._DURATION_RULE_RE.match(duration)
        if merged:
            duration = merged.group(1)
            rule = merged.group(2)
        if not rule:
            return None
        return nickname, duration, rule

    @staticmethod
    def normalize_mute_command(command: str) -> str:
        fields = LLMClient.parse_mute_command_fields(command)
        if not fields:
            return command.strip()
        nickname, duration, rule = fields
        rule_id = RulesConfig.extract_rule_id(rule)
        if rule_id in ML_ALLOWED_RULE_IDS:
            expected = RulesConfig.expected_duration(rule_id)
            if expected:
                duration = expected
        tail = ""
        parts = command.split()
        if len(parts) > 4:
            tail = " " + " ".join(parts[4:])
        return f"/tempmute {nickname} {duration} {rule}{tail}".strip()

    @staticmethod
    def is_allowed_ml_rule(reason: str) -> bool:
        rule_id = RulesConfig.extract_rule_id(reason)
        return bool(rule_id and rule_id in ML_ALLOWED_RULE_IDS)

    @staticmethod
    def _is_mild_38_message(text: str) -> bool:
        lowered = text.lower().strip()
        patterns = (
            r"^ебать\s+",
            r"\bебать\s+(?:почему|зачем|как|че|чё|ну|он|она|это|так)\b",
            r"\bебать\s+(?:коин|кайф|дорог|много|стоит)\b",
            r"\bпиздец\s+(?:защ\w*|охран\w*|крут\w*|жест\w*|имб\w*|норм\w*)",
            r"\bалл\s+отдам\s+бесплатно\b",
            r"\bв\s+душе\s+не\s+ебу\b",
            r"\bебать\s+не\s+встать\b",
            r"\bпиздуй\b",
            r"\bна\s+(?:тебя|него|нее|них|вас|меня)\s+не\s+пиздил",
            r"\bне\s+пиздил",
            r"^пизде?ж$",
            r"\bпиздишь\b",
        )
        return any(re.search(pattern, lowered) for pattern in patterns)

    @staticmethod
    def _sanitize_sexual_scan_text(lowered: str) -> str:
        text = lowered
        replacements = (
            r"д(?:а)?хуя",
            r"ни\s*хуя",
            r"не\s*хуя",
            r"ни\s*хуе",
            r"не\s*хуе",
            r"пиздец\s+(?:защ\w*|охран\w*|жест\w*|имб\w*|крут\w*|норм\w*)",
            r"\bпиздуй\b",
            r"\bна\s+(?:тебя|него|нее|них|вас|меня)\s+не\s+пиздил\w*",
            r"\bне\s+пиздил\w*",
            r"\bпизде?ж\b",
            r"\bпиздишь\b",
        )
        for pattern in replacements:
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def _looks_like_sexual(text: str) -> bool:
        if LLMClient._is_mild_38_message(text):
            return False
        lowered = text.lower()
        if LLMClient._GAME_HOLE_RE.search(lowered):
            return False
        scan = LLMClient._sanitize_sexual_scan_text(lowered)
        if any(marker in scan for marker in LLMClient._STRONG_SEXUAL_MARKERS):
            return True
        return any(word in scan for word in LLMClient._WEAK_SEXUAL_WORDS)

    @staticmethod
    def _looks_like_giveaway_or_contest(text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in LLMClient._GIVEAWAY_37_MARKERS)

    @staticmethod
    def _looks_like_chat_game(text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in LLMClient._CHAT_GAME_37_MARKERS)

    @staticmethod
    def _looks_like_family_insult(text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in LLMClient._FAMILY_MARKERS)

    _BARE_PUNISHMENT_TAG_RE = re.compile(
        r"^\s*[^\s+]+\s*\+\s*(?:бан|ban|мут|mut)\s*$",
        re.IGNORECASE,
    )

    @staticmethod
    def _is_bare_punishment_tag(text: str) -> bool:
        return bool(LLMClient._BARE_PUNISHMENT_TAG_RE.match(text.strip()))

    @staticmethod
    def _looks_like_threat(text: str) -> bool:
        lowered = text.lower()
        if LLMClient._is_bare_punishment_tag(lowered):
            return False
        if "+бан" in lowered or "+мут" in lowered or "+ban" in lowered:
            return True
        markers = (
            "забаню",
            "замучу",
            "забанят",
            "замучат",
            "дам бан",
            "дам мут",
            "получишь бан",
            "получишь мут",
        )
        return any(marker in lowered for marker in markers)

    @staticmethod
    def reject_false_mute(command: str, batch) -> str | None:
        fields = LLMClient.parse_mute_command_fields(command)
        if not fields:
            return "некорректный формат команды"
        nickname, duration, reason = fields
        rule_id = RulesConfig.extract_rule_id(reason)
        if not rule_id:
            return "нет номера правила в команде"
        if rule_id not in ML_ALLOWED_RULE_IDS and rule_id not in MANUAL_ONLY_RULES:
            return f"{rule_id}: правило не в автомуте (разрешены только 3.4–3.10)"
        message = next(
            (msg for msg in batch if msg.nickname.lower() == nickname.lower()),
            None,
        )
        if not message:
            return None
        text = message.text
        if LLMClient._looks_like_mute_dispute(text):
            return "спор по муту, не нарушение"
        if looks_like_trade_ad(text):
            return "торговля/реклама, не нарушение чата"
        if looks_like_begging(text):
            return "попрошайничество, не нарушение чата"
        if reason.startswith("2.3"):
            return "2.3: только ручная модерация (взлом аккаунта)"
        if reason.startswith("3.10"):
            if not LLMClient._looks_like_threat(text):
                return "3.10: в сообщении нет угрозы наказанием"
        elif reason.startswith("3.6"):
            if not LLMClient._looks_like_family_insult(text):
                return "3.6: нет упоминания родных"
        elif reason.startswith("3.4"):
            if HeuristicChecker.has_gibberish_spam(text):
                return "3.4: спам-символы (3.3), не оскорбление"
            if not LLMClient._looks_like_strong_insult(text):
                return "3.4: нет явного оскорбления"
        elif reason.startswith("3.7"):
            if LLMClient._looks_like_giveaway_or_contest(text):
                return "3.7: конкурс/розыгрыш, не чат-игра"
            if not LLMClient._looks_like_chat_game(text):
                return "3.7: нет провокации чат-игры"
        elif reason.startswith("3.8"):
            if not LLMClient._looks_like_sexual(text):
                return "3.8: нет явного сексуального контента"
        elif reason.startswith("3.12"):
            if not LLMClient._looks_like_punishment_interference(text):
                return "3.12: нет вмешательства в чужое наказание"
        elif reason.startswith("3.9"):
            if LLMClient._is_ingame_kill_talk(text):
                return "3.9: убийство в игровом контексте"
        return None

    @staticmethod
    def parse_verdict(result: str) -> tuple[str, str | None]:
        lines = [line.strip() for line in result.splitlines() if line.strip()]
        if not lines:
            return "invalid", None

        for line in reversed(lines):
            lower = line.lower()
            if lower.startswith("/tempmute"):
                command = LLMClient.extract_mute_command(line) or line.strip()
                return "mute", command
            if lower == "none":
                return "none", None

        if result.lower().strip() == "none":
            return "none", None

        command = LLMClient.extract_mute_command(result)
        if command:
            return "mute", command

        return "invalid", None
