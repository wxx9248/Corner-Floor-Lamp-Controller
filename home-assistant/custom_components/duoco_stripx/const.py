"""Constants for the duoCo StripX integration."""
from __future__ import annotations

DOMAIN = "duoco_stripx"

CONF_UDP_PORT = "udp_port"
DEFAULT_UDP_PORT = 8737

# Prefix used to fold scenes into the light's effect list alongside the
# animation modes (their ids live in different command spaces).
SCENE_EFFECT_PREFIX = "Scene: "
