try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

try:
    from PIL import ImageGrab
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False
    ImageGrab = None

try:
    import requests
    REQUESTS_AVAILABLE = True
    _http_session = requests.Session()
    _http_session.trust_env = False
except Exception:
    REQUESTS_AVAILABLE = False
    requests = None
    _http_session = None


def http_session():
    return _http_session

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except Exception:
    COLORAMA_AVAILABLE = False

    class Fore:
        GREEN = ""
        YELLOW = ""
        RED = ""

    class Style:
        RESET_ALL = ""

try:
    from rapidocr_onnxruntime import RapidOCR  # noqa: F401
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False
