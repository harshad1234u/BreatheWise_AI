import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  fetchCities,
  fetchAirQuality,
  fetchPollutantMap,
  fetchAirWindow,
  generateDailyPlan,
} from '@/lib/api';
import type { HouseholdProfile } from '@/types/plan';

const mockFetch = vi.fn();
global.fetch = mockFetch as unknown as typeof fetch;

describe('API Client', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('fetchCities returns parsed city metadata on HTTP 200', async () => {
    const cities = [{ id: 'delhi', name: 'Delhi NCR', state: 'Delhi', latitude: 28.6139, longitude: 77.209, waqi_keyword: 'delhi' }];
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => cities,
    });

    const result = await fetchCities();
    expect(result).toEqual(cities);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/cities$/),
      expect.objectContaining({ cache: 'no-store' })
    );
  });

  it('fetchCities returns fallback metro list on network failure', async () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    mockFetch.mockRejectedValueOnce(new Error('Network down'));

    const result = await fetchCities();
    expect(result.length).toBe(6);
    expect(result.map((c) => c.id)).toContain('delhi');
    errSpy.mockRestore();
  });

  it('fetchAirQuality constructs city query parameter and throws on non-OK HTTP status', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 503 });
    await expect(fetchAirQuality('mumbai')).rejects.toThrow('Air quality API returned HTTP 503');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/air-quality?city=mumbai'),
      expect.any(Object)
    );
  });

  it('fetchPollutantMap passes city and pollutant parameters', async () => {
    const payload = { selected_city: 'Delhi NCR', selected_pollutant: 'no2', stations: [] };
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => payload });

    const res = await fetchPollutantMap('delhi', 'no2');
    expect(res.selected_pollutant).toBe('no2');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/map/pollutants?city=delhi&pollutant=no2'),
      expect.any(Object)
    );
  });

  it('fetchAirWindow includes optional duration and is_vulnerable query params', async () => {
    const payload = { city: 'Delhi NCR', status: 'available' };
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => payload });

    await fetchAirWindow('delhi', 'walking', 2, true);
    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toContain('city=delhi');
    expect(calledUrl).toContain('activity=walking');
    expect(calledUrl).toContain('duration=2');
    expect(calledUrl).toContain('is_vulnerable=true');
  });

  it('generateDailyPlan sends POST JSON body with profile', async () => {
    const profile: HouseholdProfile = {
      profile_id: 'guest_test',
      display_name: 'Test User',
      city: 'delhi',
      preferred_station_id: null,
      persona: 'general',
      age_groups: ['adult'],
      has_respiratory_sensitivity: false,
      has_cardiovascular_sensitivity: false,
      commute_mode: 'metro_train',
      has_air_purifier: false,
      kitchen_ventilation_type: 'exhaust_fan',
      activity_preferences: ['Walking'],
    };
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ plan_id: 'plan_1' }) });

    const res = await generateDailyPlan('delhi', profile);
    expect(res.plan_id).toBe('plan_1');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/plan\/generate$/),
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
    );
  });
});
