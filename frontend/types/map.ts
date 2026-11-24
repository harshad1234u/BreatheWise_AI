export interface StationMapPoint {
  station_id: string;
  station_name: string;
  latitude: number;
  longitude: number;
  concentration: number | null;
  cpcb_sub_index: number | null;
  sub_index_category: 'Good' | 'Satisfactory' | 'Moderate' | 'Poor' | 'Very Poor' | 'Severe' | 'Unavailable';
  observed_at: string;
  data_provider: string;
  source_type: 'ground_station' | 'atmospheric_model' | 'unavailable';
  freshness_status: 'live' | 'stale' | 'unavailable';
  quality_confidence: 'high' | 'moderate' | 'low' | 'unverified';
}

export interface MapSummary {
  total_stations: number;
  reporting_stations: number;
  min_concentration: number | null;
  max_concentration: number | null;
  avg_concentration: number | null;
  data_provenance_note: string;
}

export interface PollutantMapResponse {
  selected_city: string;
  city_center_lat: number;
  city_center_lng: number;
  selected_pollutant: string;
  pollutant_name: string;
  unit: string;
  stations: StationMapPoint[];
  summary: MapSummary;
}
