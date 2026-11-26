export type MapMeasurementType =
  | 'raw_concentration'
  | 'provider_index'
  | 'cpcb_sub_index'
  | 'model_estimate'
  | 'unavailable';

export interface StationMapPoint {
  station_id: string;
  station_name: string;
  latitude: number;
  longitude: number;
  measurement_type: MapMeasurementType;
  concentration: number | null;
  cpcb_sub_index: number | null;
  sub_index_category: 'Good' | 'Satisfactory' | 'Moderate' | 'Poor' | 'Very Poor' | 'Severe' | 'Unavailable';
  provider_index: number | null;
  provider_index_name: string | null;
  provider_index_category: string | null;
  unavailable_reason: string | null;
  observed_at: string | null;
  data_provider: string;
  source_type: 'ground_station' | 'atmospheric_model' | 'unavailable';
  freshness_status: 'live' | 'stale' | 'expired' | 'unavailable';
  quality_confidence: 'high' | 'moderate' | 'low' | 'unverified';
}

export interface MapSummary {
  total_stations: number;
  valid_response_stations: number;
  reporting_stations: number;
  measurement_mode: 'raw_concentration' | 'provider_index' | 'model_estimate' | 'mixed' | 'unavailable';
  concentration_stations: number;
  provider_index_stations: number;
  model_stations: number;
  stale_stations: number;
  unavailable_stations: number;
  min_concentration: number | null;
  max_concentration: number | null;
  avg_concentration: number | null;
  min_provider_index: number | null;
  max_provider_index: number | null;
  avg_provider_index: number | null;
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
