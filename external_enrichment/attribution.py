"""Attribution helpers for enrichment providers."""


def get_attribution(provider: str) -> str:
    """Get attribution text for a provider."""
    attributions = {
        "open_meteo": "Weather data from Open-Meteo.com",
        "nager_date": "Public holiday data from Nager.Date API",
    }
    return attributions.get(provider, f"Data from {provider}")


def get_user_agent() -> str:
    """Get User-Agent for external API calls."""
    return "LiMa-Device-Gateway/1.0 (Educational Project; contact@example.com)"
