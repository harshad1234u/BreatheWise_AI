import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from app.schemas.air_quality import CityMetadata, RegionType

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "india_cities.json"


class IndiaCityCatalog:
    """
    Single centralized geographic catalog for BreatheWise AI covering all 28 Indian States
    and all 8 Union Territories. Uses immutable catalog entries and returns fresh copies per call
    so no request can mutate process-wide city metadata or coverage status.
    """

    def __init__(self, data_path: Path = DATA_FILE):
        with open(data_path, "r", encoding="utf-8") as f:
            raw_items = json.load(f)

        self._cities: Tuple[CityMetadata, ...] = tuple(CityMetadata(**item) for item in raw_items)
        self._by_id: Dict[str, CityMetadata] = {c.id.lower(): c for c in self._cities}

    def all_cities(self) -> List[CityMetadata]:
        return [c.model_copy(deep=True) for c in self._cities]

    def find_city(self, identifier: str) -> Optional[CityMetadata]:
        if not identifier:
            return None
        needle = identifier.lower().strip()
        if needle in self._by_id:
            return self._by_id[needle].model_copy(deep=True)

        for city in self._cities:
            if city.name.lower() == needle or city.waqi_keyword.lower() == needle:
                return city.model_copy(deep=True)
            if any(alias.lower() == needle for alias in city.aliases):
                return city.model_copy(deep=True)

        # Partial substring match as a fallback for search queries like "delhi" -> "Delhi NCR"
        for city in self._cities:
            if needle in city.name.lower() or any(needle in alias.lower() for alias in city.aliases):
                return city.model_copy(deep=True)
        return None

    def query(
        self,
        q: Optional[str] = None,
        state: Optional[str] = None,
        region_type: Optional[RegionType] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[CityMetadata]:
        results: List[CityMetadata] = list(self._cities)

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
        return [c.model_copy(deep=True) for c in sliced]

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
