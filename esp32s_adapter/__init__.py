"""ESP32S_XYZ protocol adapter for LiMa device gateway.

Bridges lima-device-v1 protocol to esp32S_XYZ Edge-C protocol.
"""

from .protocol import lima_to_edge_c_task, edge_c_to_lima_event, generate_route_policy

__all__ = ["lima_to_edge_c_task", "edge_c_to_lima_event", "generate_route_policy"]
