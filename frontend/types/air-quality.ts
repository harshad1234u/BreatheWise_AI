export type SourceType = 'ground_station' | 'atmospheric_model' | 'stale_cache' | 'unavailable';
export type DataStatus = 'live' | 'stale' | 'partial' | 'unavailable';
export type ConfidenceScore = 'high' | 'moderate' | 'low' | 'unverified';
export type IndexType =
  | 'official_cpcb_naqi'
  | 'indicative_particulate_subindex'
  | 'provider_index'
  | 'atmospheric_model_estimate'
  | 'unavailable';

export type IndexCategory =
  | 'Good'
  | 'Satisfactory'
  | 'Moderate'
  | 'Poor'
  | 'Very Poor'
  | 'Severe'
  | 'Unavailable';

export interface PollutantConcentration {
  value: number;
  unit: string;
  averaging_period_hours: number;
  sub_index: number | null;
}

export interface NormalizedAirObservation {
  city: string;
  locality_or_station: string | null;
  station_distance_km: number | null;
  source_type: SourceType;
  data_provider: string;
  observed_at: string;
  fetched_at: string;
  data_status: DataStatus;
  confidence_score: ConfidenceScore;
  index_type: IndexType;
  index_value: number | null;
  index_category: IndexCategory;
  methodology_disclosure: string;
  pm25: PollutantConcentration | null;
  pm10: PollutantConcentration | null;
  no2: PollutantConcentration | null;
  so2: PollutantConcentration | null;
  co: PollutantConcentration | null;
  o3: PollutantConcentration | null;
  nh3: PollutantConcentration | null;
  pb: PollutantConcentration | null;
}

export interface CityMetadata {
  id: string;
  name: string;
  state: string;
  latitude: number;
  longitude: number;
  waqi_keyword: string;
}
