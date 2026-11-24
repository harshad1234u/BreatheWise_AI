from abc import ABC, abstractmethod
from typing import Optional
from app.schemas.air_quality import NormalizedAirObservation


class AirQualityProvider(ABC):
    """Abstract interface that all air quality data providers must implement."""

    @abstractmethod
    async def get_air_quality(
        self,
        city: str,
        latitude: float,
        longitude: float,
        station_id: Optional[str] = None
    ) -> Optional[NormalizedAirObservation]:
        """Fetches and normalizes air quality observations."""
        pass
