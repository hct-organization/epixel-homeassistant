"""Constants for the ePiXeL bridge.

Every number here also appears in PROTOCOL.md. If the two ever disagree,
PROTOCOL.md wins -- the device firmware was written against that document.
"""

DOMAIN = "epixel"
API_BASE = "/api/epixel"
PROTOCOL_VERSION = 2

CONF_TOKEN = "token"
CONF_DEVICE_NAME = "device_name"
CONF_PAGES = "pages"
CONF_ICONS = "icons"          # per-page: {entity_id: icon name}

# --- Pairing safeguards (all three together are what make 4 digits enough) ---
PAIR_TTL_S = 180          # how long a code stays valid
PAIR_MAX_PENDING = 3      # concurrent pairing requests accepted
PAIR_MAX_ATTEMPTS = 5     # wrong-code entries before the flow gives up

# --- Layout limits (device screen is 320x480; six boxes -> ~138 px per row) ---
MAX_PAGES = 8
MAX_BOXES_PER_PAGE = 6
NAME_MAX = 22             # the screen truncates box titles at this width

# --- Long polling ---
LONGPOLL_MAX_S = 55       # the device asks for 25; this is the safety ceiling

# --- History / charts ---
HISTORY_POINTS = 60       # downsample target (~400 bytes on the wire)
HISTORY_MAX_HOURS = 168

# Domains the screen can actuate.
#
# Before adding a domain here, make sure the device renders the `sw` type for
# it correctly. A button that looks enabled but does nothing is a failure mode
# this product has deliberately engineered out.
SWITCHABLE_DOMAINS = ("switch", "light", "input_boolean", "fan")

# Domains a user may place on a page.
SUPPORTED_DOMAINS = ("sensor", "binary_sensor", "switch", "light", "input_boolean", "fan")

# state_class values that make a numeric sensor eligible for a chart.
GRAPHABLE_STATE_CLASSES = ("measurement", "total", "total_increasing")

# --- Dimming ---
#
# One press of the dim control moves by this much. Ten percent gives a visible
# change without making a full sweep tedious: off to full in ten presses.
DIM_STEP = 10
DIM_MIN = 5                   # below this a light reads as off, so we stop here

# --- Preview ---
#
# The preview shows entity names and states, so it is not public. It is opened
# from the options flow -- which only an authenticated Home Assistant user can
# reach -- and the key it carries expires.
PREVIEW_TTL_S = 3600

# Physical screen the preview reproduces.
SCREEN_W = 320
SCREEN_H = 480
