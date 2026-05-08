"""Central configuration for steady-hanrahan pipeline."""
import os

# --- Paths ---
FONT_DIR = "assets/fonts"
LOGO_PATH = "assets/images/logo_cfca.png"
TMP_DIR = "tmp"
SLIDES_DIR = "tmp/slides"
AUDIO_DIR = "tmp/audio"
OUTPUT_DIR = "tmp/output"

# --- Video ---
RESOLUTION = (1920, 1080)
FPS = 24
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
ENCODE_PRESET = "fast"
ENCODE_THREADS = 4

# --- Slide Design ---
COLORS = {
    "bg_deep":  "#1A1033",
    "bg_card":  "#231645",
    "gold":     "#C9A84C",
    "cream":    "#F5EDD8",
    "muted":    "#B8A89A",
    "red":      "#8B0000",
    "white":    "#FFFFFF",
}

MARGIN = 80          # px from each edge
RULE_Y_TOP = 180     # y-position of top gold rule
RULE_Y_BOT = 1020    # y-position of bottom gold rule
RULE_THICKNESS = 3
LOGO_SIZE = (120, 120)
LOGO_LARGE_SIZE = (300, 300)

FONT_SIZES = {
    "title":    72,
    "heading":  56,
    "body":     42,
    "label":    36,
    "meta":     32,
}

MAX_CHARS_PER_LINE = 55
MAX_WORDS_PER_SLIDE = 170

# --- TTS ---
VOICE = "en-AU-NatashaNeural"
VOICE_FALLBACK = "en-AU-WilliamNeural"
TTS_RATE = "+0%"
TTS_PITCH = "+0Hz"

# --- AI ---
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# --- YouTube ---
YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
YOUTUBE_TOKEN_URI = "https://oauth2.googleapis.com/token"
YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_CATEGORY_ID = "27"  # Education
YOUTUBE_PRIVACY = "public"
YOUTUBE_TAGS = [
    "Catholic", "Daily Mass", "Mass Readings", "CFCA",
    "Australia", "Catholic Filipino", "Gospel", "Scripture", "Faith",
    "Liturgy", "Reflection", "Prayer",
]

# --- Readings Source ---
UNIVERSALIS_URL = "https://universalis.com/Australia/{date}/Mass.htm"
