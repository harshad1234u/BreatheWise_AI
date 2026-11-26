import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CitySelector } from '@/components/CitySelector';
import { AirQualityHero } from '@/components/AirQualityHero';
import { ProvenanceBanner } from '@/components/ProvenanceBanner';
import { ProfileSelector } from '@/components/ProfileSelector';
import { PollutantMap, buildStationPopupElement } from '@/components/PollutantMap';

const mockLeafletRemove = vi.fn();
const mockClearLayers = vi.fn();
const mockSetView = vi.fn();
const mockFitBounds = vi.fn();
const mockMapFactory = vi.fn(() => ({
  setView: mockSetView,
  fitBounds: mockFitBounds,
  remove: mockLeafletRemove,
}));

vi.mock('leaflet', () => {
  const leafletMock = {
    map: mockMapFactory,
    tileLayer: vi.fn(() => ({ addTo: vi.fn() })),
    featureGroup: vi.fn(() => ({
      addTo: vi.fn().mockReturnThis(),
      clearLayers: mockClearLayers,
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
import type { CityMetadata, NormalizedAirObservation } from '@/types/air-quality';
import type { PollutantMapResponse, StationMapPoint } from '@/types/map';
import type { HouseholdProfile } from '@/types/plan';

const mockCities: CityMetadata[] = [
  { id: 'delhi', name: 'Delhi NCR', state: 'Delhi', latitude: 28.6139, longitude: 77.209, waqi_keyword: 'delhi' },
  { id: 'bengaluru', name: 'Bengaluru', state: 'Karnataka', latitude: 12.9716, longitude: 77.5946, waqi_keyword: 'bangalore' },
];

const mockObservation: NormalizedAirObservation = {
  city: 'Delhi NCR',
  locality_or_station: 'Mandir Marg, Delhi',
  station_distance_km: null,
  source_type: 'ground_station',
  data_provider: 'WAQI (Official CPCB Ground Feed)',
  observed_at: '2026-11-26T10:00:00Z',
  fetched_at: '2026-11-26T10:05:00Z',
  data_status: 'live',
  confidence_score: 'high',
  index_type: 'indicative_particulate_subindex',
  index_value: 273,
  index_category: 'Poor',
  methodology_disclosure: 'Indicative Real-time Sub-Index calculated using CPCB particulate breakpoints.',
  pm25: { value: 112, unit: 'µg/m³', averaging_period_hours: 1, sub_index: 273 },
  pm10: { value: 71, unit: 'µg/m³', averaging_period_hours: 1, sub_index: 71 },
  no2: null,
  so2: null,
  co: null,
  o3: null,
  nh3: null,
  pb: null,
};

const baseProfile: HouseholdProfile = {
  profile_id: 'guest_default',
  display_name: 'Delhi NCR Family (Sample)',
  city: 'delhi',
  preferred_station_id: null,
  persona: 'parent',
  age_groups: ['child', 'adult'],
  has_respiratory_sensitivity: true,
  has_cardiovascular_sensitivity: false,
  commute_mode: 'two_wheeler',
  has_air_purifier: true,
  kitchen_ventilation_type: 'exhaust_fan',
  activity_preferences: ['School drop-off'],
};

describe('Core UI Components', () => {
  it('CitySelector sets aria-pressed and invokes onSelectCity on click', () => {
    const onSelect = vi.fn();
    render(
      <CitySelector
        cities={mockCities}
        selectedCityId="delhi"
        onSelectCity={onSelect}
        isLoading={false}
      />
    );

    const delhiBtn = screen.getByRole('button', { name: 'Delhi NCR' });
    const blrBtn = screen.getByRole('button', { name: 'Bengaluru' });
    expect(delhiBtn).toHaveAttribute('aria-pressed', 'true');
    expect(blrBtn).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(blrBtn);
    expect(onSelect).toHaveBeenCalledWith('bengaluru');
  });

  it('CitySelector All India explorer filters cities by search alias and state', () => {
    const panIndiaCities: CityMetadata[] = [
      ...mockCities,
      {
        id: 'thiruvananthapuram',
        name: 'Thiruvananthapuram',
        state: 'Kerala',
        region_type: 'state',
        aliases: ['trivandrum'],
        latitude: 8.5241,
        longitude: 76.9366,
        waqi_keyword: 'thiruvananthapuram',
      },
    ];
    const onSelect = vi.fn();
    render(
      <CitySelector
        cities={panIndiaCities}
        selectedCityId="delhi"
        onSelectCity={onSelect}
        isLoading={false}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /All India/i }));
    const searchInput = screen.getByLabelText(/Search City, District, State, or Alias/i);
    fireEvent.change(searchInput, { target: { value: 'trivandrum' } });

    const tvmBtn = screen.getByRole('button', { name: /Thiruvananthapuram/i });
    expect(tvmBtn).toBeInTheDocument();
    fireEvent.click(tvmBtn);
    expect(onSelect).toHaveBeenCalledWith('thiruvananthapuram');
  });

  it('AirQualityHero displays station name, index value, and category label', () => {
    render(<AirQualityHero observation={mockObservation} />);
    expect(screen.getByText('Mandir Marg, Delhi')).toBeInTheDocument();
    expect(screen.getByText('273')).toBeInTheDocument();
    expect(screen.getByText('Poor')).toBeInTheDocument();
  });

  it('AirQualityHero identifies WAQI provider_index as US-EPA AQI rather than CPCB Index Band', () => {
    render(
      <AirQualityHero
        observation={{
          ...mockObservation,
          index_type: 'provider_index',
          index_value: 190,
          index_category: 'Poor',
          provider_index_category: 'Unhealthy',
          pm25: { value: 190, unit: 'US-EPA Sub-Index', averaging_period_hours: 1, sub_index: null },
        }}
      />
    );
    expect(screen.getByText('190')).toBeInTheDocument();
    expect(screen.getByText('WAQI US-EPA AQI')).toBeInTheDocument();
    expect(screen.getByText('Unhealthy')).toBeInTheDocument();
    expect(screen.queryByText(/CPCB Index Band/i)).not.toBeInTheDocument();
  });

  it('ProvenanceBanner clearly distinguishes indicative sub-index and model estimates', () => {
    const { rerender } = render(<ProvenanceBanner observation={mockObservation} />);
    expect(screen.getByText('Live Ground Monitor Telemetry')).toBeInTheDocument();
    expect(screen.getByText('Indicative Real-Time Sub-Index')).toBeInTheDocument();

    rerender(
      <ProvenanceBanner
        observation={{
          ...mockObservation,
          source_type: 'atmospheric_model',
          index_type: 'atmospheric_model_estimate',
          data_provider: 'Open-Meteo (CAMS Regional Model)',
        }}
      />
    );
    expect(screen.getByText('Atmospheric Model Projection (CAMS)')).toBeInTheDocument();
    expect(screen.getByText('Atmospheric Model Estimate')).toBeInTheDocument();
  });

  it('ProfileSelector supports accessible customizer form controls and profile reset', () => {
    const onChange = vi.fn();
    const onGenerate = vi.fn();
    render(
      <ProfileSelector
        currentProfile={{ ...baseProfile, persona: 'athlete', has_respiratory_sensitivity: false }}
        onProfileChange={onChange}
        onGeneratePlan={onGenerate}
        isLoading={false}
      />
    );

    const customizeBtn = screen.getByRole('button', { name: /Customize Sensitivities/i });
    expect(customizeBtn).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(customizeBtn);
    expect(customizeBtn).toHaveAttribute('aria-expanded', 'true');

    // Verify htmlFor/id association on Primary Persona select
    expect(screen.getByLabelText('Primary Persona')).toBeInTheDocument();
    expect(screen.getByLabelText('Commute Mode')).toBeInTheDocument();
    expect(screen.getByLabelText('Kitchen Ventilation')).toBeInTheDocument();

    // Reset profile back to default
    const resetBtn = screen.getByRole('button', { name: /Reset household profile/i });
    fireEvent.click(resetBtn);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        profile_id: 'guest_default',
        persona: 'parent',
        has_respiratory_sensitivity: true,
      })
    );
  });

  it('PollutantMap renders WAQI provider_index station card, summary, and dynamic legend', async () => {
    const mockMapResp: PollutantMapResponse = {
      selected_city: 'Guwahati',
      city_center_lat: 26.1445,
      city_center_lng: 91.7362,
      selected_pollutant: 'pm25',
      pollutant_name: 'PM2.5 (Fine Particulates)',
      unit: 'µg/m³',
      stations: [
        {
          station_id: 'station_501',
          station_name: 'Guwahati Station 1',
          latitude: 26.18,
          longitude: 91.74,
          measurement_type: 'provider_index',
          concentration: null,
          cpcb_sub_index: null,
          sub_index_category: 'Unavailable',
          provider_index: 50,
          provider_index_name: 'WAQI US-EPA AQI',
          provider_index_category: 'Good',
          unavailable_reason: 'Raw concentration not provided by WAQI; displaying WAQI US-EPA sub-index',
          observed_at: '2026-11-26T14:00:00Z',
          data_provider: 'WAQI Provider Feed',
          source_type: 'ground_station',
          freshness_status: 'live',
          quality_confidence: 'high',
        },
      ],
      summary: {
        total_stations: 1,
        valid_response_stations: 1,
        reporting_stations: 1,
        measurement_mode: 'provider_index',
        concentration_stations: 0,
        provider_index_stations: 1,
        model_stations: 0,
        stale_stations: 0,
        unavailable_stations: 0,
        min_concentration: null,
        max_concentration: null,
        avg_concentration: null,
        min_provider_index: 50,
        max_provider_index: 50,
        avg_provider_index: 50,
        data_provenance_note: 'Displaying WAQI provider sub-indices.',
      },
    };

    const origFetch = global.fetch;
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockMapResp,
    }) as unknown as typeof fetch;

    try {
      render(<PollutantMap cityId="guwahati" cityName="Guwahati" />);

      expect(await screen.findByText('50 (US-EPA AQI)')).toBeInTheDocument();
      expect(screen.getByText('WAQI Provider Index')).toBeInTheDocument();
      expect(screen.getByText('WAQI INDEX — PM25')).toBeInTheDocument();
      expect(screen.getByText('Raw concentration — Not provided')).toBeInTheDocument();
      expect(screen.queryByText('Not Monitored')).not.toBeInTheDocument();
    } finally {
      global.fetch = origFetch;
    }
  });

  it('buildStationPopupElement safely escapes malicious markup and preserves ordinary station details', () => {
    const xssPayload = '<img src=x onerror=alert(1)>';
    const maliciousStation: StationMapPoint = {
      station_id: 'station_xss',
      station_name: `Anand Vihar ${xssPayload}`,
      latitude: 28.64,
      longitude: 77.31,
      measurement_type: 'raw_concentration',
      concentration: 84.5,
      cpcb_sub_index: 181,
      sub_index_category: 'Moderate',
      provider_index: null,
      provider_index_name: null,
      provider_index_category: null,
      unavailable_reason: `Reason ${xssPayload}`,
      observed_at: '2026-11-26T14:00:00Z',
      data_provider: `Provider ${xssPayload}`,
      source_type: 'ground_station',
      freshness_status: `live ${xssPayload}` as unknown as StationMapPoint['freshness_status'],
      quality_confidence: 'high',
    };

    const popupEl = buildStationPopupElement(maliciousStation, `µg/m³ ${xssPayload}`);
    expect(popupEl).toBeInstanceOf(HTMLElement);
    // Zero executable HTML tags injected
    expect(popupEl.querySelectorAll('img, script, svg, iframe').length).toBe(0);
    // Literal text preserved safely via textContent
    expect(popupEl.textContent).toContain(`Anand Vihar ${xssPayload}`);
    expect(popupEl.textContent).toContain(`Provider ${xssPayload}`);
    expect(popupEl.textContent).toContain(`84.5 µg/m³ ${xssPayload}`);
    expect(popupEl.textContent).toContain(`Reason ${xssPayload}`);

    // Ordinary provider_index popup rendering
    const ordinaryStation: StationMapPoint = {
      station_id: 'station_guwahati',
      station_name: 'Railway Colony, Guwahati',
      latitude: 26.18,
      longitude: 91.78,
      measurement_type: 'provider_index',
      concentration: null,
      cpcb_sub_index: null,
      sub_index_category: 'Unavailable',
      provider_index: 151,
      provider_index_name: 'WAQI US-EPA AQI',
      provider_index_category: 'Unhealthy',
      unavailable_reason: 'Raw concentration not provided by WAQI',
      observed_at: '2026-11-26T12:30:00Z',
      data_provider: 'WAQI Feed (CPCB/SPCB Station Network)',
      source_type: 'ground_station',
      freshness_status: 'stale',
      quality_confidence: 'moderate',
    };
    const normalEl = buildStationPopupElement(ordinaryStation, 'µg/m³');
    expect(normalEl.textContent).toContain('Railway Colony, Guwahati');
    expect(normalEl.textContent).toContain('151');
    expect(normalEl.textContent).toContain('Not provided by source');
    expect(normalEl.textContent).toContain('WAQI Feed (CPCB/SPCB Station Network)');
  });

  it('PollutantMap disposes Leaflet map on unmount, aborts superseded city fetches, and ignores AbortError', async () => {
    mockLeafletRemove.mockClear();
    mockClearLayers.mockClear();
    mockMapFactory.mockClear();

    const makeResp = (city: string, idxVal: number): PollutantMapResponse => ({
      selected_city: city,
      city_center_lat: 28.6,
      city_center_lng: 77.2,
      selected_pollutant: 'pm25',
      pollutant_name: 'PM2.5 (Fine Particulates)',
      unit: 'µg/m³',
      stations: [
        {
          station_id: `stn_${city}`,
          station_name: `${city} Station`,
          latitude: 28.6,
          longitude: 77.2,
          measurement_type: 'provider_index',
          concentration: null,
          cpcb_sub_index: null,
          sub_index_category: 'Unavailable',
          provider_index: idxVal,
          provider_index_name: 'WAQI US-EPA AQI',
          provider_index_category: 'Moderate',
          unavailable_reason: null,
          observed_at: '2026-11-26T14:00:00Z',
          data_provider: 'WAQI Provider Feed',
          source_type: 'ground_station',
          freshness_status: 'live',
          quality_confidence: 'high',
        },
      ],
      summary: {
        total_stations: 1,
        valid_response_stations: 1,
        reporting_stations: 1,
        measurement_mode: 'provider_index',
        concentration_stations: 0,
        provider_index_stations: 1,
        model_stations: 0,
        stale_stations: 0,
        unavailable_stations: 0,
        min_concentration: null,
        max_concentration: null,
        avg_concentration: null,
        min_provider_index: idxVal,
        max_provider_index: idxVal,
        avg_provider_index: idxVal,
        data_provenance_note: `Displaying ${city}`,
      },
    });

    const signals: AbortSignal[] = [];
    let resolveDelhi!: (val: unknown) => void;
    const origFetch = global.fetch;
    global.fetch = vi.fn((url: string | URL | Request, init?: RequestInit) => {
      if (init?.signal) signals.push(init.signal);
      const u = String(url);
      if (u.includes('city=delhi')) {
        return new Promise((res, rej) => {
          resolveDelhi = res;
          init?.signal?.addEventListener('abort', () => {
            rej(new DOMException('Aborted', 'AbortError'));
          });
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => makeResp('Mumbai', 112),
      });
    }) as unknown as typeof fetch;

    try {
      const { rerender, unmount } = render(<PollutantMap cityId="delhi" cityName="Delhi NCR" />);
      // Switch quickly to Mumbai while Delhi is still pending
      rerender(<PollutantMap cityId="mumbai" cityName="Mumbai" />);

      expect(await screen.findByText('112 (US-EPA AQI)')).toBeInTheDocument();
      expect(signals.length).toBeGreaterThanOrEqual(2);
      expect(signals[0].aborted).toBe(true);
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      // Even if a stale resolver tries to resolve later, Mumbai stays rendered
      if (resolveDelhi) resolveDelhi({ ok: true, json: async () => makeResp('Delhi NCR', 199) });
      expect(screen.getByText('112 (US-EPA AQI)')).toBeInTheDocument();

      await waitFor(() => {
        expect(mockMapFactory).toHaveBeenCalledTimes(1);
      });

      unmount();
      expect(mockClearLayers).toHaveBeenCalled();
      expect(mockLeafletRemove).toHaveBeenCalledTimes(1);
    } finally {
      global.fetch = origFetch;
    }
  });

  it('PollutantMap renders alert on genuine API failure and preserves controlled pollutant across city switches', async () => {
    const origFetch = global.fetch;
    global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 500 }) as unknown as typeof fetch;

    try {
      const onPollutantChange = vi.fn();
      const { rerender } = render(
        <PollutantMap
          cityId="delhi"
          cityName="Delhi NCR"
          selectedPollutant="no2"
          onSelectPollutant={onPollutantChange}
        />
      );

      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent('Unable to Load Pollutant Map');
      expect(alert).toHaveTextContent('HTTP 500');

      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          selected_city: 'Mumbai',
          city_center_lat: 19.07,
          city_center_lng: 72.87,
          selected_pollutant: 'no2',
          pollutant_name: 'NO2 (Nitrogen Dioxide)',
          unit: 'µg/m³',
          stations: [],
          summary: {
            total_stations: 0,
            valid_response_stations: 0,
            reporting_stations: 0,
            measurement_mode: 'unavailable',
            concentration_stations: 0,
            provider_index_stations: 0,
            model_stations: 0,
            stale_stations: 0,
            unavailable_stations: 0,
            min_concentration: null,
            max_concentration: null,
            avg_concentration: null,
            min_provider_index: null,
            max_provider_index: null,
            avg_provider_index: null,
            data_provenance_note: 'No stations.',
          },
        }),
      }) as unknown as typeof fetch;

      rerender(
        <PollutantMap
          cityId="mumbai"
          cityName="Mumbai"
          selectedPollutant="no2"
          onSelectPollutant={onPollutantChange}
        />
      );

      expect(await screen.findByText(/No Monitoring Stations Available/i)).toBeInTheDocument();
      const no2Btn = screen.getByRole('button', { name: /NO₂/i });
      expect(no2Btn).toHaveAttribute('aria-pressed', 'true');
    } finally {
      global.fetch = origFetch;
    }
  });
});
