import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import type { NormalizedAirObservation } from '@/types/air-quality';
import type { AirWindowResponse } from '@/types/air-window';
import type { DailyPlanResponse, HouseholdProfile } from '@/types/plan';

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
    fetchAirWindow: vi.fn(),
  };
});

import * as api from '@/lib/api';
import { ForecastWindow } from '@/components/ForecastWindow';
import { DailyPlanView } from '@/components/DailyPlanView';
import { PollutantGrid } from '@/components/PollutantGrid';
import { HealthGuidance } from '@/components/HealthGuidance';

const fullEightObs: NormalizedAirObservation = {
  city: 'Delhi NCR',
  locality_or_station: 'RK Puram',
  station_distance_km: 1.5,
  source_type: 'ground_station',
  data_provider: 'CPCB Monitor',
  observed_at: '2026-11-26T10:00:00Z',
  fetched_at: '2026-11-26T10:02:00Z',
  data_status: 'live',
  confidence_score: 'high',
  index_type: 'official_cpcb_naqi',
  index_value: 250,
  index_category: 'Poor',
  methodology_disclosure: 'Evaluated via CPCB NAQI.',
  pm25: { value: 105, unit: 'µg/m³', averaging_period_hours: 1, sub_index: 250 },
  pm10: { value: 190, unit: 'µg/m³', averaging_period_hours: 1, sub_index: 160 },
  no2: { value: 45, unit: 'µg/m³', averaging_period_hours: 1, sub_index: 56 },
  so2: { value: 0.0, unit: 'µg/m³', averaging_period_hours: 1, sub_index: 0 },
  co: { value: 1.5, unit: 'mg/m³', averaging_period_hours: 1, sub_index: 75 },
  o3: { value: 60, unit: 'µg/m³', averaging_period_hours: 1, sub_index: 60 },
  nh3: { value: 120, unit: 'µg/m³', averaging_period_hours: 1, sub_index: 30 },
  pb: { value: 0.4, unit: 'µg/m³', averaging_period_hours: 1, sub_index: null },
};

const baseProfile: HouseholdProfile = {
  profile_id: 'guest_ext',
  city: 'delhi',
  persona: 'commuter',
  age_groups: ['adult'],
  has_respiratory_sensitivity: false,
  has_cardiovascular_sensitivity: false,
  commute_mode: 'metro_train',
  has_air_purifier: false,
  kitchen_ventilation_type: 'exhaust_fan',
};

const richAirWindow: AirWindowResponse = {
  city: 'Mumbai',
  activity: 'running',
  duration_hours: 1,
  generated_at: '2026-11-26T10:00:00Z',
  data_provider: 'Open-Meteo CAMS',
  data_provenance_type: 'atmospheric_model',
  confidence: 'moderate',
  status: 'available',
  disclaimer: 'Model forecast is indicative only.',
  best_window: {
    start_time: '13:00',
    end_time: '14:00',
    duration_hours: 1,
    average_comparative_score: 72,
    score_label: 'Lowest Forecast Pollution Period',
    dominant_pollutant: 'pm25',
    strenuous_outdoor_allowed: true,
    activity_suitability: 'Suitable for moderate outdoor running.',
    precautionary_notes: ['Stay hydrated'],
  },
  peak_pollution_window: {
    start_time: '21:00',
    end_time: '22:00',
    duration_hours: 1,
    average_comparative_score: 215,
    score_label: 'Higher Pollution Period',
    dominant_pollutant: 'no2',
    strenuous_outdoor_allowed: false,
    activity_suitability: 'Shift exercise indoors.',
    precautionary_notes: [],
  },
  alternative_windows: [
    {
      start_time: '15:00',
      end_time: '16:00',
      duration_hours: 1,
      average_comparative_score: 88,
      score_label: 'Comparatively Better Window',
      dominant_pollutant: 'pm10',
      strenuous_outdoor_allowed: true,
      activity_suitability: 'Moderate alternative',
      precautionary_notes: [],
    },
  ],
  hourly_forecast: [
    {
      timestamp: '2026-11-26T13:00:00Z',
      hour_label: '01:00 PM',
      pm25: 42,
      pm10: 68,
      o3: 28,
      no2: 19,
      so2: 7,
      co: 0.5,
      wind_speed: 9.1,
      comparative_score: 72,
      dominant_pollutant: 'pm25',
      category_label: 'Satisfactory',
    },
  ],
};

describe('F-13 Extended Component Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('ForecastWindow renders valid windows, switches activity, toggles trace details, and handles insufficient data', async () => {
    vi.mocked(api.fetchAirWindow)
      .mockResolvedValueOnce(richAirWindow)
      .mockResolvedValueOnce({ ...richAirWindow, activity: 'walking' })
      .mockResolvedValueOnce({
        city: 'Leh',
        activity: 'running',
        duration_hours: 1,
        generated_at: '2026-11-26T10:00:00Z',
        data_provider: 'Open-Meteo CAMS',
        data_provenance_type: 'unavailable',
        confidence: 'unverified',
        status: 'insufficient_data',
        disclaimer: 'Insufficient forecast hours available.',
        best_window: null,
        peak_pollution_window: null,
        alternative_windows: [],
        hourly_forecast: [],
      });

    const { rerender } = render(<ForecastWindow cityId="mumbai" cityName="Mumbai" />);

    // Loading state visible before promise resolves
    expect(screen.getByText(/Calculating diurnal multi-pollutant trajectory/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('13:00 - 14:00')).toBeInTheDocument();
      expect(screen.getByText('21:00 - 22:00')).toBeInTheDocument();
      expect(screen.getByText('15:00 - 16:00')).toBeInTheDocument();
    });

    // Breakdown toggle updates aria-expanded
    const toggleBtn = screen.getByRole('button', { name: /Show PM2.5, PM10 & O3 traces/i });
    expect(toggleBtn).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggleBtn);
    expect(toggleBtn).toHaveAttribute('aria-expanded', 'true');

    // Selecting Walking triggers updated fetch
    const walkBtn = screen.getByRole('button', { name: /Walking \/ School Commute/i });
    fireEvent.click(walkBtn);
    await waitFor(() => {
      expect(api.fetchAirWindow).toHaveBeenCalledWith(
        'mumbai',
        'walking',
        1,
        false,
        expect.any(Object)
      );
      expect(walkBtn).toHaveAttribute('aria-pressed', 'true');
    });

    // Insufficient data state renders cleanly without crashing
    rerender(<ForecastWindow cityId="leh" cityName="Leh" />);
    await waitFor(() => {
      expect(screen.getByText('Insufficient forecast hours available.')).toBeInTheDocument();
    });
  });

  it('DailyPlanView renders provider badges, optional precautions, indoor tips, and sustainable alternatives', () => {
    const plan: DailyPlanResponse = {
      plan_id: 'plan_groq_1',
      generated_at: '2026-11-26T10:05:00Z',
      ai_provider_used: 'groq',
      is_fallback: false,
      data_provenance: fullEightObs,
      household_profile: baseProfile,
      safety_guidance: {
        band: 'Poor',
        dominant_pollutant: 'PM2.5',
        data_confidence: 'high',
        source_type: 'ground_station',
        exposure_concerns: ['Particulates'],
        constraints: {
          calculated_band: 'Poor',
          dominant_pollutant: 'PM2.5',
          outdoor_exertion_level: 'light_only',
          vulnerable_activity_restriction: 'indoor_only',
          ventilation_guidance: 'midday_only',
          respirator_advisory: 'n95_advised_prolonged',
          indoor_mitigation_required: true,
          fallback_indoor_activity: 'Indoor cycling',
          source_reference: 'CPCB NAQI',
        },
        general_population_guidance: 'Avoid intense workouts.',
        children_guidance: 'Indoor play.',
        senior_guidance: 'Rest indoors.',
        respiratory_guidance: 'Keep inhaler ready.',
        commuters_athletes_guidance: 'Use N95 mask.',
        indoor_ventilation_guidance: 'Midday only.',
        indoor_cooking_guidance: 'Run exhaust.',
        authoritative_sources: ['CPCB'],
      },
      morning: [
        {
          period: 'morning',
          time_window: '08:00 AM - 09:00 AM',
          activity: 'Metro Commute',
          location_type: 'transit',
          intensity: 'light',
          explanation: 'Enclosed AC metro lowers inhalation dose.',
          precautions: 'Wear N95 respirator at interchange stations.',
          data_context_used: 'PM2.5 105 µg/m³',
        },
      ],
      afternoon: [
        {
          period: 'afternoon',
          time_window: '01:00 PM - 02:00 PM',
          activity: 'Brief Midday Ventilation',
          location_type: 'indoor',
          intensity: 'none',
          explanation: 'Higher boundary layer improves dispersion.',
          precautions: null,
          data_context_used: 'Diurnal trend',
        },
      ],
      evening: [],
      indoor_air_suggestions: ['Run chimney exhaust while tadka cooking.', 'Wet mop floors.'],
      sustainable_alternatives: ['Take shared electric bus for last mile.'],
      disclaimer: 'Not medical advice.',
    };

    const { rerender } = render(<DailyPlanView plan={plan} />);
    expect(screen.getByText(/Synthesized by Groq Llama 3/i)).toBeInTheDocument();
    expect(screen.getByText('Metro Commute')).toBeInTheDocument();
    expect(screen.getByText('Wear N95 respirator at interchange stations.')).toBeInTheDocument();
    expect(screen.getByText('Brief Midday Ventilation')).toBeInTheDocument();
    expect(screen.getByText('Run chimney exhaust while tadka cooking.')).toBeInTheDocument();
    expect(screen.getByText('Take shared electric bus for last mile.')).toBeInTheDocument();

    rerender(<DailyPlanView plan={{ ...plan, ai_provider_used: 'gemini', is_fallback: false }} />);
    expect(screen.getByText(/Synthesized by Google Gemini/i)).toBeInTheDocument();

    rerender(<DailyPlanView plan={{ ...plan, ai_provider_used: 'deterministic_fallback', is_fallback: true }} />);
    expect(screen.getByText(/Deterministic Public-Health Engine/i)).toBeInTheDocument();
  });

  it('PollutantGrid renders all 8 criteria pollutants including zero, mg/m³ CO, null sub-index, and missing data', () => {
    const { rerender } = render(<PollutantGrid observation={fullEightObs} />);
    expect(screen.getByText('Evaluated via CPCB sub-index breakpoints')).toBeInTheDocument();
    for (const label of ['PM2.5', 'PM10', 'NO₂', 'O₃', 'SO₂', 'CO', 'NH₃', 'Pb']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByText('0.0')).toBeInTheDocument();
    expect(screen.getByText('Sub-index: 0 • Good')).toBeInTheDocument();
    expect(screen.getByText('mg/m³')).toBeInTheDocument();
    expect(screen.getByText('--')).toBeInTheDocument();

    // Unavailable / provider_index mode
    rerender(
      <PollutantGrid
        observation={{
          ...fullEightObs,
          index_type: 'provider_index',
          pm25: null,
          pm10: null,
          no2: null,
          so2: null,
          co: null,
          o3: null,
          nh3: null,
          pb: null,
        }}
      />
    );
    expect(screen.getByText(/WAQI provider sub-indices/i)).toBeInTheDocument();
    expect(screen.getAllByText('--').length).toBeGreaterThanOrEqual(8);
  });

  it('HealthGuidance adapts advisory content across all CPCB severity bands and unavailable telemetry', () => {
    const { rerender } = render(<HealthGuidance category="Good" />);
    expect(screen.getByText(/Outdoor exercise and active transit/i)).toBeInTheDocument();

    rerender(<HealthGuidance category="Moderate" />);
    expect(screen.getByText(/schedule periodic hydration and rest breaks/i)).toBeInTheDocument();

    rerender(<HealthGuidance category="Poor" />);
    expect(screen.getByText(/wet mopping \(pocha\)/i)).toBeInTheDocument();

    rerender(<HealthGuidance category="Very Poor" />);
    expect(screen.getByText(/Keep prescribed inhalers/i)).toBeInTheDocument();

    rerender(<HealthGuidance category="Severe" />);
    expect(screen.getByText(/Strict indoor sheltering advised/i)).toBeInTheDocument();

    rerender(<HealthGuidance category="Unavailable" />);
    expect(screen.getByText('Awaiting local telemetry data.')).toBeInTheDocument();
  });
});
