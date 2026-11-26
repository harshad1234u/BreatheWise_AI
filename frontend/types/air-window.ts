export interface HourlyPollutantPoint {
  timestamp: string;
  hour_label: string;
  pm25: number | null;
  pm10: number | null;
  o3: number | null;
  no2: number | null;
  so2: number | null;
  co: number | null;
  wind_speed: number | null;
  comparative_score: number;
  dominant_pollutant: string;
  category_label: string;
}

export interface BestAirWindowPeriod {
  start_time: string;
  end_time: string;
  start_iso?: string | null;
  end_iso?: string | null;
  duration_hours: number;
  average_comparative_score: number;
  score_label:
    | 'Lowest Forecast Pollution Period'
    | 'Comparatively Better Window'
    | 'Higher Pollution Period'
    | 'Insufficient Forecast Data';
  dominant_pollutant: string;
  strenuous_outdoor_allowed: boolean;
  activity_suitability: string;
  precautionary_notes: string[];
}

export interface AirWindowResponse {
  city: string;
  activity: string;
  duration_hours: number;
  generated_at: string;
  data_provider: string;
  data_provenance_type: 'atmospheric_model' | 'unavailable';
  confidence: 'moderate' | 'low' | 'unverified';
  status: 'available' | 'insufficient_data' | 'unavailable';
  disclaimer: string;
  best_window: BestAirWindowPeriod | null;
  peak_pollution_window: BestAirWindowPeriod | null;
  alternative_windows: BestAirWindowPeriod[];
  hourly_forecast: HourlyPollutantPoint[];
}
