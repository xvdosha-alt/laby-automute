from moderator.bot import ModeratorBot
from moderator.config import Settings
from moderator.dashboard_server import start_dashboard
from moderator.mute_store import MuteStore
from moderator.rules_config import RulesConfig
from moderator.runtime_state import RuntimeState
import threading


def main():
    settings = Settings.load()
    store = MuteStore(settings)
    rules = RulesConfig(settings.data_dir)
    runtime = RuntimeState()
    start_dashboard(settings, store, runtime, rules)
    bot = ModeratorBot(settings, store, runtime, rules)
    thread = threading.Thread(target=bot.run, name="moderator-bot", daemon=True)
    thread.start()
    runtime.add_log(
        "[сервис] бот в фоне, модерация выключена — нажми «Старт модерации» во вкладке «Клиенты»",
        "yellow",
    )
    try:
        while thread.is_alive():
            thread.join(timeout=1.0)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
