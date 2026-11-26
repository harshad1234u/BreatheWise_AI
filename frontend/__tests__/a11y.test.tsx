import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import type { CityMetadata, NormalizedAirObservation } from '@/types/air-quality';
import type { AirWindowResponse } from '@/types/air-window';
import type { PollutantMapResponse } from '@/types/map';
import type { DailyPlanResponse, HouseholdProfile } from '@/types/plan';

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

vi.mock('leaflet', () => {
  const leafletMock = {
    map: vi.fn(() => ({
      setView: vi.fn(),
      fitBounds: vi.fn(),
      remove: vi.fn(),
    })),
    tileLayer: vi.fn(() => ({ addTo: vi.fn() })),
    featureGroup: vi.fn(() => ({
      addTo: vi.fn().mockReturnThis(),
      clearLayers: vi.fn(),
      addLayer: vi.fn(),
      getBounds: vi.fn(() => ({ pad: vi.fn(() => ({})) })),
    })),
    circleMarker: vi.fn(() => ({
      bindPopup: vi.fn(),
      on: vi.fn(),
    })),
  };
  return { default: leafletMock, ...leafletMock };
});

vi.mock('recharts', () => {
  const Stub = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>;
  return {
    ResponsiveContainer: Stub,
    AreaChart: () => <div data-testid="recharts-area-chart" />,
    Area: () => null,
    Line: () => null,
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
  };
});

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return {
    ...actual,
    fetchCities: vi.fn(),
    fetchCityCatalogMeta: vi.fn(),
    fetchAirQuality: vi.fn(),
    generateDailyPlan: vi.fn(),
    fetchPollutantMap: vi.fn(),
    fetchAirWindow: vi.fn(),
  };
});

import * as api from '@/lib/api';
import DashboardPage from '@/app/page';
import { ForecastWindow } from '@/components/ForecastWindow';
import { PollutantGrid } from '@/components/PollutantGrid';

const citiesFixture: CityMetadata[] = [
  { id: 'delhi', name: 'Delhi NCR', state: 'Delhi', latitude: 28.6139, longitude: 77.209, waqi_keyword: 'delhi' },
  { id: 'mumbai', name: 'Mumbai', state: 'Maharashtra', latitude: 19.076, longitude: 72.8777, waqi_keyword: 'mumbai' },
];

const obsFixture: NormalizedAirObservation = {
  city: 'Delhi NCR',
  locality_or_station: 'Mandir Marg, Delhi',
  station_distance_km: null,
  source_type: 'ground_station',
  data_provider: 'WAQI',
  observed_at: '2026-11-26T10:00:00Z',
  fetched_at: '2026-11-26T10:05:00Z',
  data_status: 'live',
  confidence_score: 'high',
  index_type: 'indicative_particulate_subindex',
  index_value: 245,
  index_category: 'Poor',
  methodology_disclosure: 'CPCB breakpoints applied.',
  pm25: { value: 103, unit: 'µg/m³', averaging_period_hours: 1, sub_index: 245 },
  pm10: { value: 180, unit: 'µg/m³', averaging_period_hours: 1, sub_index: 153 },
  no2: null,
  so2: null,
  co: null,
  o3: null,
  nh3: null,
  pb: null,
};

const airWindowFixture: AirWindowResponse = {
  city: 'Delhi NCR',
  activity: 'running',
  duration_hours: 1,
  generated_at: '2026-11-26T10:00:00Z',
  data_provider: 'Open-Meteo CAMS',
  data_provenance_type: 'atmospheric_model',
  confidence: 'moderate',
  status: 'available',
  disclaimer: 'Model estimate only',
  best_window: {
    start_time: '14:00',
    end_time: '15:00',
    duration_hours: 1,
    average_comparative_score: 120,
    score_label: 'Comparatively Better Window',
    dominant_pollutant: 'pm25',
    strenuous_outdoor_allowed: false,
    activity_suitability: 'Light outdoor errand only.',
    precautionary_notes: ['Wear N95 along arterial roads'],
  },
  peak_pollution_window: {
    start_time: '20:00',
    end_time: '21:00',
    duration_hours: 1,
    average_comparative_score: 260,
    score_label: 'Higher Pollution Period',
    dominant_pollutant: 'pm25',
    strenuous_outdoor_allowed: false,
    activity_suitability: 'Stay indoors.',
    precautionary_notes: [],
  },
  alternative_windows: [],
  hourly_forecast: [
    {
      timestamp: '2026-11-26T14:00:00Z',
      hour_label: '02:00 PM',
      pm25: 66,
      pm10: 110,
      o3: 32,
      no2: 24,
      so2: 9,
      co: 0.7,
      wind_speed: 5.5,
      comparative_score: 120,
      dominant_pollutant: 'pm25',
      category_label: 'Moderate',
    },
  ],
};

const mapFixture: PollutantMapResponse = {
  selected_city: 'Delhi NCR',
  city_center_lat: 28.6139,
  city_center_lng: 77.209,
  selected_pollutant: 'pm25',
  pollutant_name: 'PM2.5',
  unit: 'µg/m³',
  stations: [
    {
      station_id: 'delhi-1',
      station_name: 'Mandir Marg Station',
      latitude: 28.63,
      longitude: 77.2,
      measurement_type: 'raw_concentration',
      concentration: 103,
      cpcb_sub_index: 245,
      sub_index_category: 'Poor',
      provider_index: null,
      provider_index_name: null,
      provider_index_category: null,
      unavailable_reason: null,
      observed_at: '2026-11-26T10:00:00Z',
      data_provider: 'WAQI',
      source_type: 'ground_station',
      freshness_status: 'live',
      quality_confidence: 'high',
    },
  ],
  summary: {
    total_stations: 1,
    valid_response_stations: 1,
    reporting_stations: 1,
    measurement_mode: 'raw_concentration',
    concentration_stations: 1,
    provider_index_stations: 0,
    model_stations: 0,
    stale_stations: 0,
    unavailable_stations: 0,
    min_concentration: 103,
    max_concentration: 103,
    avg_concentration: 103,
    min_provider_index: null,
    max_provider_index: null,
    avg_provider_index: null,
    data_provenance_note: 'Ground measurements',
  },
};

const defaultProfile: HouseholdProfile = {
  profile_id: 'guest_default',
  display_name: 'Delhi NCR Family (Sample)',
  city: 'delhi',
  persona: 'parent',
  age_groups: ['child', 'adult'],
  has_respiratory_sensitivity: true,
  has_cardiovascular_sensitivity: false,
  commute_mode: 'two_wheeler',
  has_air_purifier: true,
  kitchen_ventilation_type: 'exhaust_fan',
};

const planFixture: DailyPlanResponse = {
  plan_id: 'plan_delhi_a11y',
  generated_at: '2026-11-26T10:05:00Z',
  ai_provider_used: 'deterministic_fallback',
  is_fallback: true,
  data_provenance: obsFixture,
  household_profile: defaultProfile,
  safety_guidance: {
    band: 'Poor',
    dominant_pollutant: 'PM2.5',
    data_confidence: 'high',
    source_type: 'ground_station',
    exposure_concerns: ['High particulate concentration'],
    constraints: {
      calculated_band: 'Poor',
      dominant_pollutant: 'PM2.5',
      outdoor_exertion_level: 'light_only',
      vulnerable_activity_restriction: 'indoor_only',
      ventilation_guidance: 'midday_only',
      respirator_advisory: 'n95_advised_prolonged',
      indoor_mitigation_required: true,
      fallback_indoor_activity: 'Indoor mobility routine',
      source_reference: 'CPCB NAQI',
    },
    general_population_guidance: 'Reduce outdoor workouts.',
    children_guidance: 'Stay indoors.',
    senior_guidance: 'Light indoor routine.',
    respiratory_guidance: 'Keep rescue inhaler ready.',
    commuters_athletes_guidance: 'Use N95 mask.',
    indoor_ventilation_guidance: 'Midday only.',
    indoor_cooking_guidance: 'Use exhaust fan.',
    authoritative_sources: ['CPCB'],
  },
  morning: [
    {
      period: 'morning',
      time_window: '07:00 AM',
      activity: 'Indoor stretch',
      location_type: 'indoor',
      intensity: 'light',
      explanation: 'Morning particulates elevated.',
      data_context_used: 'PM2.5',
    },
  ],
  afternoon: [],
  evening: [],
  indoor_air_suggestions: ['Wet mop floors instead of dry sweeping.'],
  sustainable_alternatives: ['Take enclosed Metro rail.'],
  disclaimer: 'Advisory only.',
};

function assertNoSkippedHeadingLevels(container: HTMLElement) {
  const headings = Array.from(container.querySelectorAll('h1, h2, h3, h4, h5, h6'));
  let prevLevel = 0;
  for (const h of headings) {
    const level = Number(h.tagName.slice(1));
    if (prevLevel > 0) {
      expect(level).toBeLessThanOrEqual(prevLevel + 1);
    }
    prevLevel = level;
  }
}

describe('F-10 Semantic HTML & Heading Accessibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('maintains exactly one meaningful h1 in loading state and error state', async () => {
    const deferredAqi = createDeferred<NormalizedAirObservation>();
    vi.mocked(api.fetchCities).mockResolvedValue(citiesFixture);
    vi.mocked(api.fetchCityCatalogMeta).mockResolvedValue({
      total_cities: 2,
      states_count: 2,
      union_territories_count: 0,
      states: ['Delhi', 'Maharashtra'],
      union_territories: [],
    });
    vi.mocked(api.fetchAirQuality).mockImplementationOnce(() => deferredAqi.promise);

    const { container } = render(<DashboardPage />);

    // Loading state must have landmark + single h1
    expect(screen.getByRole('banner')).toBeInTheDocument();
    expect(screen.getByRole('main')).toBeInTheDocument();
    const loadingH1s = container.querySelectorAll('h1');
    expect(loadingH1s.length).toBe(1);
    expect(loadingH1s[0].textContent?.trim().length).toBeGreaterThan(5);
    assertNoSkippedHeadingLevels(container);

    // Reject into error state
    await act(async () => {
      deferredAqi.reject(new Error('Telemetry network failure'));
    });
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Telemetry network failure');
    });

    const errorH1s = container.querySelectorAll('h1');
    expect(errorH1s.length).toBe(1);
    expect(errorH1s[0].textContent?.trim().length).toBeGreaterThan(5);
    assertNoSkippedHeadingLevels(container);
  });

  it('maintains single h1, logical heading hierarchy without skipped levels, and semantic landmarks in full dashboard state', async () => {
    vi.mocked(api.fetchCities).mockResolvedValue(citiesFixture);
    vi.mocked(api.fetchCityCatalogMeta).mockResolvedValue({
      total_cities: 2,
      states_count: 2,
      union_territories_count: 0,
      states: ['Delhi', 'Maharashtra'],
      union_territories: [],
    });
    vi.mocked(api.fetchAirQuality).mockResolvedValue(obsFixture);
    vi.mocked(api.fetchAirWindow).mockResolvedValue(airWindowFixture);
    vi.mocked(api.fetchPollutantMap).mockResolvedValue(mapFixture);
    vi.mocked(api.generateDailyPlan).mockResolvedValue(planFixture);

    const { container } = render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('Mandir Marg, Delhi')).toBeInTheDocument();
      expect(screen.getByText('Mandir Marg Station')).toBeInTheDocument();
    });

    // Generate daily plan so every dashboard section renders
    fireEvent.click(screen.getByRole('button', { name: /Generate Daily Routine/i }));
    await waitFor(() => {
      expect(screen.getByText('Indoor stretch')).toBeInTheDocument();
    });

    expect(screen.getByRole('banner')).toBeInTheDocument();
    expect(screen.getByRole('main')).toBeInTheDocument();
    expect(screen.getByRole('contentinfo')).toBeInTheDocument();

    const h1s = container.querySelectorAll('h1');
    expect(h1s.length).toBe(1);
    expect(container.querySelectorAll('h2').length).toBeGreaterThanOrEqual(5);
    expect(container.querySelectorAll('section').length).toBeGreaterThanOrEqual(5);
    assertNoSkippedHeadingLevels(container);
  });
});

describe('F-11 Chart Accessibility, Contrast & Reduced Motion', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('ForecastWindow provides accessible chart region, textual summary, tabular fallback, and non-color severity text', async () => {
    vi.mocked(api.fetchAirWindow).mockResolvedValueOnce(airWindowFixture);

    render(<ForecastWindow cityId="delhi" cityName="Delhi NCR" />);

    await waitFor(() => {
      expect(screen.getByText('14:00 - 15:00')).toBeInTheDocument();
    });

    // Accessible chart region & labeled chart container
    const chartImg = screen.getByRole('img', { name: /24-hour diurnal pollution forecast chart/i });
    expect(chartImg).toBeInTheDocument();

    // Summary description + visible severity category labels (not color-only)
    expect(screen.getByText(/Comparative diurnal exposure analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/Score:\s*120\s*•\s*Moderate/i)).toBeInTheDocument();
    expect(screen.getByText(/Peak Score:\s*260\s*•\s*Poor/i)).toBeInTheDocument();

    // Screen-reader / keyboard accessible tabular forecast representation
    const table = screen.getByRole('table', { name: /Hourly pollutant forecast data/i });
    expect(table).toBeInTheDocument();
    expect(table).toHaveTextContent('02:00 PM');
    expect(table).toHaveTextContent('Moderate');
    expect(table).toHaveTextContent('µg/m³');
  });

  it('PollutantGrid includes textual severity category alongside sub-index color badge', () => {
    render(<PollutantGrid observation={obsFixture} />);
    expect(screen.getByText(/Sub-index:\s*245\s*•\s*Poor/i)).toBeInTheDocument();
    expect(screen.getByText(/Sub-index:\s*153\s*•\s*Moderate/i)).toBeInTheDocument();
  });

  it('globals.css defines prefers-reduced-motion: reduce overrides', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const cssPath = path.resolve(process.cwd(), 'app/globals.css');
    const css = fs.readFileSync(cssPath, 'utf8');
    expect(css).toContain('@media (prefers-reduced-motion: reduce)');
    expect(css).toContain('animation-duration');
    expect(css).toContain('transition-duration');
  });
});
