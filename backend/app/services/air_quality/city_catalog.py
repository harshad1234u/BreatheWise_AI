import json
from pathlib import Path
from typing import Dict, List, Literal, Optional
from app.schemas.air_quality import CityMetadata

CoverageStatus = Literal[
    "ground_monitoring_available",
    "model_forecast_available",
    "both_available",
    "no_current_data",
    "unsupported_location",
]

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "india_cities.json"


class IndiaCityCatalog:
    """
    Single centralized geographic catalog for BreatheWise AI covering all 28 Indian States
    and all 8 Union Territories. Separates geographic discovery from live telemetry availability
    and tracks verified observed provider coverage dynamically without fabricating station data.
    """

    def __init__(self, data_path: Path = DATA_FILE):
        with open(data_path, "r", encoding="utf-8") as f:
            raw_items = json.load(f)

        self._cities: List[CityMetadata] = [CityMetadata(**item) for item in raw_items]
        self._by_id: Dict[str, CityMetadata] = {c.id.lower(): c for c in self._cities}
        # Runtime-observed coverage tracker (never pre-claimed as guaranteed live ground stations)
        self._observed_coverage: Dict[str, CoverageStatus] = {}

    def all_cities(self) -> List[CityMetadata]:
        return [self._with_observed_status(c) for c in self._cities]

    def _with_observed_status(self, city: CityMetadata) -> CityMetadata:
        status = self._observed_coverage.get(city.id, "model_forecast_available")
        return city.model_copy(update={"availability_status": status})

    def record_observed_availability(
        self,
        city_id: str,
        has_ground: bool,
        has_model: bool,
    ) -> None:
        key = city_id.lower().strip()
        if key not in self._by_id:
            return
        if has_ground and has_model:
            self._observed_coverage[key] = "both_available"
        elif has_ground:
            self._observed_coverage[key] = "ground_monitoring_available"
        elif has_model:
            self._observed_coverage[key] = "model_forecast_available"
        else:
            self._observed_coverage[key] = "no_current_data"

    def find_city(self, identifier: str) -> Optional[CityMetadata]:
        if not identifier:
            return None
        needle = identifier.lower().strip()
        if needle in self._by_id:
            return self._with_observed_status(self._by_id[needle])

        for city in self._cities:
            if city.name.lower() == needle or city.waqi_keyword.lower() == needle:
                return self._with_observed_status(city)
            if any(alias.lower() == needle for alias in city.aliases):
                return self._with_observed_status(city)

        # Partial substring match as a fallback for search queries like "delhi" -> "Delhi NCR"
        for city in self._cities:
            if needle in city.name.lower() or any(needle in alias.lower() for alias in city.aliases):
                return self._with_observed_status(city)
        return None

    def query(
        self,
        q: Optional[str] = None,
        state: Optional[str] = None,
        region_type: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[CityMetadata]:
        results = self._cities

        if region_type:
            rt = region_type.lower().strip()
            results = [c for c in results if c.region_type.lower() == rt]

        if state:
            st = state.lower().strip()
            results = [c for c in results if c.state.lower() == st]

        if q:
            needle = q.lower().strip()
            results = [
                c
                for c in results
                if (
                    needle in c.id.lower()
                    or needle in c.name.lower()
                    or needle in c.state.lower()
                    or (c.district and needle in c.district.lower())
                    or any(needle in alias.lower() for alias in c.aliases)
                )
            ]

        sliced = results[offset:] if limit is None else results[offset : offset + limit]
        return [self._with_observed_status(c) for c in sliced]

    def summary_metadata(self) -> Dict[str, object]:
        states = sorted({c.state for c in self._cities if c.region_type == "state"})
        uts = sorted({c.state for c in self._cities if c.region_type == "union_territory"})
        return {
            "total_cities": len(self._cities),
            "states_count": len(states),
            "union_territories_count": len(uts),
            "states": states,
            "union_territories": uts,
        }


city_catalog = IndiaCityCatalog()
