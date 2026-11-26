import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
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
import { PollutantMap } from '@/components/PollutantMap';
import { ForecastWindow } from '@/components/ForecastWindow';
import DashboardPage from '@/app/page';

const citiesFixture: CityMetadata[] = [
  { id: 'delhi', name: 'Delhi NCR', state: 'Delhi', latitude: 28.6139, longitude: 77.209, waqi_keyword: 'delhi' },
  { id: 'mumbai', name: 'Mumbai', state: 'Maharashtra', latitude: 19.076, longitude: 72.8777, waqi_keyword: 'mumbai' },
];

function makeObservation(city: string, aqi: number): NormalizedAirObservation {
  return {
    city,
    locality_or_station: `${city} Central Station`,
    station_distance_km: null,
    source_type: 'ground_station',
    data_provider: 'WAQI',
    observed_at: '2026-11-26T10:00:00Z',
    fetched_at: '2026-11-26T10:05:00Z',
    data_status: 'live',
    confidence_score: 'high',
    index_type: 'provider_index',
    index_value: aqi,
    index_category: aqi > 200 ? 'Poor' : 'Moderate',
    methodology_disclosure: `Disclosure for ${city}`,
    pm25: { value: aqi > 200 ? 110 : 48, unit: 'µg/m³', averaging_period_hours: 1, sub_index: aqi },
    pm10: { value: 80, unit: 'µg/m³', averaging_period_hours: 1, sub_index: 80 },
    no2: null,
    so2: null,
    co: null,
    o3: null,
    nh3: null,
    pb: null,
  };
}

function makeMapPayload(city: string, pollutant: string, stationName: string): PollutantMapResponse {
  return {
    selected_city: city,
    city_center_lat: city === 'Mumbai' ? 19.076 : 28.6139,
    city_center_lng: city === 'Mumbai' ? 72.8777 : 77.209,
    selected_pollutant: pollutant,
    pollutant_name: pollutant.toUpperCase(),
    unit: 'µg/m³',
    stations: [
      {
        station_id: `${city}-1`,
        station_name: stationName,
        latitude: 28.61,
        longitude: 77.21,
        measurement_type: 'raw_concentration',
        concentration: 77,
        cpcb_sub_index: 145,
        sub_index_category: 'Moderate',
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
      min_concentration: 77,
      max_concentration: 77,
      avg_concentration: 77,
      min_provider_index: null,
      max_provider_index: null,
      avg_provider_index: null,
      data_provenance_note: 'Test provenance note',
    },
  };
}

function makeAirWindow(city: string, startTime: string, endTime: string): AirWindowResponse {
  return {
    city,
    activity: 'running',
    duration_hours: 1,
    generated_at: '2026-11-26T10:00:00Z',
    data_provider: 'Open-Meteo CAMS',
    data_provenance_type: 'atmospheric_model',
    confidence: 'moderate',
    status: 'available',
    disclaimer: 'Model estimate only',
    best_window: {
      start_time: startTime,
      end_time: endTime,
      duration_hours: 1,
      average_comparative_score: 65,
      score_label: 'Lowest Forecast Pollution Period',
      dominant_pollutant: 'pm25',
      strenuous_outdoor_allowed: true,
      activity_suitability: `${city} outdoor activity window`,
      precautionary_notes: ['Stay hydrated'],
    },
    peak_pollution_window: {
      start_time: '20:00',
      end_time: '21:00',
      duration_hours: 1,
      average_comparative_score: 210,
      score_label: 'Higher Pollution Period',
      dominant_pollutant: 'pm25',
      strenuous_outdoor_allowed: false,
      activity_suitability: 'Avoid peak hour',
      precautionary_notes: [],
    },
    alternative_windows: [],
    hourly_forecast: [
      {
        timestamp: '2026-11-26T12:00:00Z',
        hour_label: '12:00 PM',
        pm25: 40,
        pm10: 65,
        o3: 30,
        no2: 20,
        so2: 10,
        co: 0.4,
        wind_speed: 6.2,
        comparative_score: 65,
        dominant_pollutant: 'pm25',
        category_label: 'Satisfactory',
      },
    ],
  };
}

function makePlan(city: string, profile: HouseholdProfile): DailyPlanResponse {
  return {
    plan_id: `plan_${city}_${profile.persona}`,
    generated_at: '2026-11-26T10:05:00Z',
    ai_provider_used: 'deterministic_fallback',
    is_fallback: true,
    data_provenance: makeObservation(city, 140),
    household_profile: profile,
    safety_guidance: {
      band: 'Moderate',
      dominant_pollutant: 'PM2.5',
      data_confidence: 'high',
      source_type: 'ground_station',
      exposure_concerns: ['Morning traffic particulate spike'],
      constraints: {
        calculated_band: 'Moderate',
        dominant_pollutant: 'PM2.5',
        outdoor_exertion_level: 'moderate_with_breaks',
        vulnerable_activity_restriction: 'monitor_symptoms',
        ventilation_guidance: 'close_traffic_peaks',
        respirator_advisory: 'optional_dust_zones',
        indoor_mitigation_required: true,
        fallback_indoor_activity: 'Indoor mobility routine',
        source_reference: 'CPCB NAQI',
      },
      general_population_guidance: 'Moderate air quality.',
      children_guidance: 'Monitor symptoms.',
      senior_guidance: 'Prefer shorter sessions.',
      respiratory_guidance: 'Keep inhaler accessible.',
      commuters_athletes_guidance: 'Avoid peak highways.',
      indoor_ventilation_guidance: 'Air rooms midday.',
      indoor_cooking_guidance: 'Run exhaust fan.',
      authoritative_sources: ['CPCB'],
    },
    morning: [
      {
        period: 'morning',
        time_window: '07:00 AM - 09:00 AM',
        activity: `${city} (${profile.persona}) Routine`,
        location_type: 'indoor',
        intensity: 'light',
        explanation: `Plan tailored for ${city} and ${profile.persona}`,
        data_context_used: 'CPCB PM2.5',
      },
    ],
    afternoon: [],
    evening: [],
    indoor_air_suggestions: ['Run exhaust fan during tadka cooking.'],
    sustainable_alternatives: ['Take enclosed metro rail instead of two-wheeler.'],
    disclaimer: 'Advisory only',
  };
}

describe('F-09 Frontend Concurrency, Timeout & Lifecycle Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('PollutantMap ignores late-resolving non-aborted stale city response after newer city resolves', async () => {
    const delhiDeferred = createDeferred<PollutantMapResponse>();
    const mumbaiDeferred = createDeferred<PollutantMapResponse>();

    vi.mocked(api.fetchPollutantMap)
      .mockImplementationOnce(() => delhiDeferred.promise)
      .mockImplementationOnce(() => mumbaiDeferred.promise);

    const { rerender } = render(
      <PollutantMap cityId="delhi" cityName="Delhi NCR" selectedPollutant="pm25" />
    );

    rerender(<PollutantMap cityId="mumbai" cityName="Mumbai" selectedPollutant="pm25" />);

    // Newer request (Mumbai) resolves FIRST
    await act(async () => {
      mumbaiDeferred.resolve(makeMapPayload('Mumbai', 'pm25', 'Bandra Kurla Complex'));
    });

    await waitFor(() => {
      expect(screen.getByText('Bandra Kurla Complex')).toBeInTheDocument();
    });

    // Older request (Delhi) ignores AbortSignal and resolves LATE (after Mumbai!)
    await act(async () => {
      delhiDeferred.resolve(makeMapPayload('Delhi NCR', 'pm25', 'Mandir Marg Stale Station'));
    });

    expect(screen.getByText('Bandra Kurla Complex')).toBeInTheDocument();
    expect(screen.queryByText('Mandir Marg Stale Station')).not.toBeInTheDocument();
  });

  it('ForecastWindow aborts stale fetches, ignores non-aborted late responses, renders errors, and cleans up on unmount', async () => {
    const d1 = createDeferred<AirWindowResponse>();
    const d2 = createDeferred<AirWindowResponse>();
    const signals: AbortSignal[] = [];

    vi.mocked(api.fetchAirWindow)
      .mockImplementationOnce((_c, _a, _d, _v, signal) => {
        if (signal) signals.push(signal);
        return d1.promise;
      })
      .mockImplementationOnce((_c, _a, _d, _v, signal) => {
        if (signal) signals.push(signal);
        return d2.promise;
      });

    const { rerender, unmount } = render(<ForecastWindow cityId="delhi" cityName="Delhi NCR" />);
    rerender(<ForecastWindow cityId="mumbai" cityName="Mumbai" />);

    expect(signals[0]?.aborted).toBe(true);

    // Resolve Mumbai first, then late-resolve stale Delhi
    await act(async () => {
      d2.resolve(makeAirWindow('Mumbai', '06:00', '07:00'));
    });
    await waitFor(() => {
      expect(screen.getByText('06:00 - 07:00')).toBeInTheDocument();
    });

    await act(async () => {
      d1.resolve(makeAirWindow('Delhi NCR', '22:00', '23:00'));
    });
    expect(screen.getByText('06:00 - 07:00')).toBeInTheDocument();
    expect(screen.queryByText('22:00 - 23:00')).not.toBeInTheDocument();

    // Unmount aborts in-flight fetch cleanly
    const d3 = createDeferred<AirWindowResponse>();
    vi.mocked(api.fetchAirWindow).mockImplementationOnce((_c, _a, _d, _v, signal) => {
      if (signal) signals.push(signal);
      return d3.promise;
    });
    rerender(<ForecastWindow cityId="chennai" cityName="Chennai" />);
    const pendingSignal = signals[2];
    expect(pendingSignal?.aborted).toBe(false);
    unmount();
    expect(pendingSignal?.aborted).toBe(true);

    // Non-abort error displays alert cleanly
    vi.mocked(api.fetchAirWindow).mockRejectedValueOnce(new Error('Forecast offline'));
    render(<ForecastWindow cityId="delhi" cityName="Delhi NCR" />);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Forecast offline');
    });
  });

  it('DashboardPage handles rapid city switching (Delhi -> Mumbai -> Delhi) while preserving persona & pollutant selection', async () => {
    vi.mocked(api.fetchCities).mockResolvedValue(citiesFixture);
    vi.mocked(api.fetchCityCatalogMeta).mockResolvedValue({
      total_cities: 2,
      states_count: 2,
      union_territories_count: 0,
      states: ['Delhi', 'Maharashtra'],
      union_territories: [],
    });
    vi.mocked(api.fetchAirWindow).mockImplementation(async (cityId) =>
      makeAirWindow(cityId === 'mumbai' ? 'Mumbai' : 'Delhi NCR', '06:00', '07:00')
    );
    vi.mocked(api.fetchPollutantMap).mockImplementation(async (cityId, pollutant) =>
      makeMapPayload(
        cityId === 'mumbai' ? 'Mumbai' : 'Delhi NCR',
        pollutant || 'pm25',
        `${cityId}-${pollutant}-station`
      )
    );

    const delhiAqiCalls: Array<ReturnType<typeof createDeferred<NormalizedAirObservation>>> = [];
    const mumbaiAqiCalls: Array<ReturnType<typeof createDeferred<NormalizedAirObservation>>> = [];
    const delhiPlanCalls: Array<ReturnType<typeof createDeferred<DailyPlanResponse>>> = [];
    const mumbaiPlanCalls: Array<ReturnType<typeof createDeferred<DailyPlanResponse>>> = [];

    vi.mocked(api.fetchAirQuality).mockImplementation((city) => {
      const d = createDeferred<NormalizedAirObservation>();
      if (city === 'mumbai') {
        mumbaiAqiCalls.push(d);
      } else {
        delhiAqiCalls.push(d);
      }
      return d.promise;
    });

    vi.mocked(api.generateDailyPlan).mockImplementation((city) => {
      const d = createDeferred<DailyPlanResponse>();
      if (city === 'mumbai') {
        mumbaiPlanCalls.push(d);
      } else {
        delhiPlanCalls.push(d);
      }
      return d.promise;
    });

    render(<DashboardPage />);

    // Initial Delhi load finishes
    await waitFor(() => expect(delhiAqiCalls.length).toBe(1));
    await act(async () => {
      delhiAqiCalls[0].resolve(makeObservation('Delhi NCR', 260));
    });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Delhi NCR Central Station' })).toBeInTheDocument();
    });

    // Change persona to Senior Citizen and map pollutant to NO2
    const seniorPersonaBtn = screen.getByRole('button', { name: /Senior Citizen/i });
    fireEvent.click(seniorPersonaBtn);

    const no2Btn = await waitFor(() => screen.getByRole('button', { name: /NO₂/i }));
    fireEvent.click(no2Btn);
    await waitFor(() => {
      expect(no2Btn).toHaveAttribute('aria-pressed', 'true');
    });

    // Rapid switch: Delhi -> Mumbai -> Delhi before Mumbai settles
    const mumbaiBtn = screen.getByRole('button', { name: 'Mumbai' });
    const delhiBtn = screen.getByRole('button', { name: 'Delhi NCR' });

    fireEvent.click(mumbaiBtn);
    fireEvent.click(delhiBtn);

    const seniorProfile: HouseholdProfile = {
      profile_id: 'guest_default',
      display_name: 'Senior Citizen (Sample Persona)',
      city: 'delhi',
      persona: 'senior',
      age_groups: ['senior'],
      has_respiratory_sensitivity: false,
      has_cardiovascular_sensitivity: true,
      commute_mode: 'walking',
      has_air_purifier: true,
      kitchen_ventilation_type: 'exhaust_fan',
    };

    // Resolve final Delhi AQI FIRST
    await waitFor(() => expect(delhiAqiCalls.length).toBe(2));
    await act(async () => {
      delhiAqiCalls[1].resolve(makeObservation('Delhi NCR', 285));
    });

    // Resolve intermediate stale Mumbai AQI LATE (after Delhi-2 already rendered!)
    if (mumbaiAqiCalls[0]) {
      await act(async () => {
        mumbaiAqiCalls[0].resolve(makeObservation('Mumbai', 110));
      });
    }

    // Generate plan after rapid switch to confirm persona & commute are preserved
    const genBtn = screen.getByRole('button', { name: /Generate/i });
    fireEvent.click(genBtn);
    await waitFor(() => expect(delhiPlanCalls.length).toBe(1));
    await act(async () => {
      delhiPlanCalls[0].resolve(makePlan('Delhi NCR', seniorProfile));
    });

    // Delhi-2 remains rendered, stale Mumbai does NOT overwrite, and senior + commute + NO2 stay preserved!
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Delhi NCR Central Station' })).toBeInTheDocument();
      expect(screen.getByText('Delhi NCR (senior) Routine')).toBeInTheDocument();
    });
    expect(screen.queryByRole('heading', { name: 'Mumbai Central Station' })).not.toBeInTheDocument();
    expect(screen.queryByText('Mumbai (senior) Routine')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /NO₂/i })).toHaveAttribute('aria-pressed', 'true');
    const lastDelhiPlanArgs = vi.mocked(api.generateDailyPlan).mock.calls.filter(([c]) => c === 'delhi').at(-1)?.[1];
    expect(lastDelhiPlanArgs?.persona).toBe('senior');
    expect(lastDelhiPlanArgs?.commute_mode).toBe('walking');
  });

  it('DashboardPage ignores late-resolving stale Delhi response after switching to Mumbai', async () => {
    vi.mocked(api.fetchCities).mockResolvedValue(citiesFixture);
    vi.mocked(api.fetchCityCatalogMeta).mockResolvedValue({
      total_cities: 2,
      states_count: 2,
      union_territories_count: 0,
      states: ['Delhi', 'Maharashtra'],
      union_territories: [],
    });
    vi.mocked(api.fetchAirWindow).mockResolvedValue(makeAirWindow('Mumbai', '06:00', '07:00'));
    vi.mocked(api.fetchPollutantMap).mockResolvedValue(makeMapPayload('Mumbai', 'pm25', 'Mumbai Map Station'));

    const delhiAqi = createDeferred<NormalizedAirObservation>();
    const mumbaiAqi = createDeferred<NormalizedAirObservation>();

    vi.mocked(api.fetchAirQuality).mockImplementation((city) =>
      city === 'mumbai' ? mumbaiAqi.promise : delhiAqi.promise
    );
    vi.mocked(api.generateDailyPlan).mockImplementation((city, prof) =>
      Promise.resolve(makePlan(city === 'mumbai' ? 'Mumbai' : 'Delhi NCR', prof))
    );

    render(<DashboardPage />);

    // Switch immediately to Mumbai while initial Delhi request is still pending
    const mumbaiBtn = await waitFor(() => screen.getByRole('button', { name: 'Mumbai' }));
    fireEvent.click(mumbaiBtn);

    await act(async () => {
      mumbaiAqi.resolve(makeObservation('Mumbai', 105));
    });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Mumbai Central Station' })).toBeInTheDocument();
    });

    // Now resolve the slow initial Delhi request (ignoring AbortSignal)
    await act(async () => {
      delhiAqi.resolve(makeObservation('Delhi NCR', 310));
    });

    expect(screen.getByRole('heading', { name: 'Mumbai Central Station' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Delhi NCR Central Station' })).not.toBeInTheDocument();
    expect(screen.queryByText('Delhi NCR (parent) Routine')).not.toBeInTheDocument();
  });

  it('DashboardPage executes complete user workflow: select city, view pollutants, change map pollutant & forecast activity, generate plan & recover from errors', async () => {
    vi.mocked(api.fetchCities).mockResolvedValue(citiesFixture);
    vi.mocked(api.fetchCityCatalogMeta).mockResolvedValue({
      total_cities: 2,
      states_count: 2,
      union_territories_count: 0,
      states: ['Delhi', 'Maharashtra'],
      union_territories: [],
    });
    vi.mocked(api.fetchAirQuality)
      .mockResolvedValueOnce(makeObservation('Delhi NCR', 230))
      .mockResolvedValueOnce(makeObservation('Mumbai', 95));
    vi.mocked(api.fetchPollutantMap).mockImplementation(async (cityId, pollutant) =>
      makeMapPayload(
        cityId === 'mumbai' ? 'Mumbai' : 'Delhi NCR',
        pollutant || 'pm25',
        `${cityId}-${pollutant}-station`
      )
    );
    vi.mocked(api.fetchAirWindow).mockImplementation(async (cityId, activity) => ({
      ...makeAirWindow(cityId === 'mumbai' ? 'Mumbai' : 'Delhi NCR', '07:00', '08:00'),
      activity: activity || 'running',
    }));

    const runnerProfile: HouseholdProfile = {
      profile_id: 'guest_default',
      display_name: 'Outdoor Athlete / Runner (Sample Persona)',
      city: 'mumbai',
      persona: 'athlete',
      age_groups: ['adult'],
      has_respiratory_sensitivity: false,
      has_cardiovascular_sensitivity: false,
      commute_mode: 'metro_train',
      has_air_purifier: false,
      kitchen_ventilation_type: 'chimney',
    };

    vi.mocked(api.generateDailyPlan)
      .mockRejectedValueOnce(new Error('Plan service temporarily unavailable'))
      .mockResolvedValueOnce(makePlan('Mumbai', runnerProfile));

    render(<DashboardPage />);

    // 1. Wait for initial Delhi load
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Delhi NCR Central Station' })).toBeInTheDocument();
    });

    // 2. Switch city to Mumbai
    fireEvent.click(screen.getByRole('button', { name: 'Mumbai' }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Mumbai Central Station' })).toBeInTheDocument();
      expect(screen.getByText('Criteria Pollutants Breakdown')).toBeInTheDocument();
    });

    // 3. Select O3 pollutant on PollutantMap
    const o3Btn = await waitFor(() => screen.getByRole('button', { name: /O₃/i }));
    fireEvent.click(o3Btn);
    await waitFor(() => {
      expect(api.fetchPollutantMap).toHaveBeenCalledWith('mumbai', 'o3', expect.any(Object));
      expect(o3Btn).toHaveAttribute('aria-pressed', 'true');
    });

    // 4. Change forecast activity preference to Walking
    const walkBtn = screen.getByRole('button', { name: /Walking \/ School Commute/i });
    fireEvent.click(walkBtn);
    await waitFor(() => {
      expect(api.fetchAirWindow).toHaveBeenCalledWith('mumbai', 'walking', 1, true, expect.any(Object));
    });

    // 5. Switch persona to Outdoor Runner & trigger plan failure then retry recovery
    fireEvent.click(screen.getByRole('button', { name: /Outdoor Runner/i }));
    fireEvent.click(screen.getByRole('button', { name: /Generate Daily Routine/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Plan service temporarily unavailable');
    });

    fireEvent.click(screen.getByRole('button', { name: /Retry Synthesis/i }));
    await waitFor(() => {
      expect(screen.getByText('Mumbai (athlete) Routine')).toBeInTheDocument();
    });
  });
});
