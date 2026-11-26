import { CityCatalogMetadata, CityMetadata, NormalizedAirObservation } from '@/types/air-quality';
import { DailyPlanResponse, HouseholdProfile } from '@/types/plan';
import { PollutantMapResponse } from '@/types/map';
import { AirWindowResponse } from '@/types/air-window';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const DEFAULT_REQUEST_TIMEOUT_MS = 15000;

export function isAbortError(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false;
  return 'name' in err && (err as { name?: unknown }).name === 'AbortError';
}

async function fetchWithCancel(
  input: string,
  init: RequestInit,
  externalSignal?: AbortSignal,
  timeoutMs: number = DEFAULT_REQUEST_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  let timedOut = false;

  if (externalSignal?.aborted) {
    controller.abort();
  }

  const onExternalAbort = () => controller.abort();
  externalSignal?.addEventListener('abort', onExternalAbort, { once: true });

  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (err: unknown) {
    if (timedOut) {
      throw new Error('Request timed out. Please try again.');
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
    externalSignal?.removeEventListener('abort', onExternalAbort);
  }
}

export async function fetchCities(
  params?: {
    q?: string;
    state?: string;
    region_type?: string;
    limit?: number;
  },
  signal?: AbortSignal
): Promise<CityMetadata[]> {
  try {
    const url = new URL(`${API_BASE_URL}/api/v1/cities`);
    if (params?.q) url.searchParams.set('q', params.q);
    if (params?.state) url.searchParams.set('state', params.state);
    if (params?.region_type) url.searchParams.set('region_type', params.region_type);
    if (params?.limit) url.searchParams.set('limit', params.limit.toString());

    const res = await fetchWithCancel(
      url.toString(),
      { cache: 'no-store' },
      signal
    );
    if (!res.ok) {
      throw new Error(`Failed to fetch cities: ${res.statusText}`);
    }
    return await res.json();
  } catch (error) {
    if (signal?.aborted || isAbortError(error)) {
      throw error;
    }
    console.error('Error fetching cities:', error);
    // Fallback metro list in case backend is warming up
    return [
      { id: 'delhi', name: 'Delhi NCR', state: 'Delhi', region_type: 'union_territory', latitude: 28.6139, longitude: 77.2090, waqi_keyword: 'delhi' },
      { id: 'mumbai', name: 'Mumbai', state: 'Maharashtra', region_type: 'state', latitude: 19.0760, longitude: 72.8777, waqi_keyword: 'mumbai' },
      { id: 'bengaluru', name: 'Bengaluru', state: 'Karnataka', region_type: 'state', latitude: 12.9716, longitude: 77.5946, waqi_keyword: 'bangalore' },
      { id: 'hyderabad', name: 'Hyderabad', state: 'Telangana', region_type: 'state', latitude: 17.3850, longitude: 78.4867, waqi_keyword: 'hyderabad' },
      { id: 'kolkata', name: 'Kolkata', state: 'West Bengal', region_type: 'state', latitude: 22.5726, longitude: 88.3639, waqi_keyword: 'kolkata' },
      { id: 'chennai', name: 'Chennai', state: 'Tamil Nadu', region_type: 'state', latitude: 13.0827, longitude: 80.2707, waqi_keyword: 'chennai' },
    ];
  }
}

export async function fetchCityCatalogMeta(signal?: AbortSignal): Promise<CityCatalogMetadata | null> {
  try {
    const res = await fetchWithCancel(`${API_BASE_URL}/api/v1/cities/catalog`, { cache: 'no-store' }, signal);
    if (!res.ok) return null;
    return await res.json();
  } catch (error) {
    if (signal?.aborted || isAbortError(error)) {
      throw error;
    }
    return null;
  }
}

export async function fetchAirQuality(
  cityId: string,
  stationId?: string,
  signal?: AbortSignal
): Promise<NormalizedAirObservation> {
  const url = new URL(`${API_BASE_URL}/api/v1/air-quality`);
  url.searchParams.set('city', cityId);
  if (stationId) {
    url.searchParams.set('station_id', stationId);
  }

  const res = await fetchWithCancel(url.toString(), { cache: 'no-store' }, signal);

  if (!res.ok) {
    throw new Error(`Air quality API returned HTTP ${res.status}`);
  }

  return await res.json();
}

export async function generateDailyPlan(
  cityId: string,
  profile: HouseholdProfile,
  stationId?: string,
  signal?: AbortSignal
): Promise<DailyPlanResponse> {
  const res = await fetchWithCancel(
    `${API_BASE_URL}/api/v1/plan/generate`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        city: cityId,
        station_id: stationId,
        profile: profile,
      }),
    },
    signal,
    25000
  );

  if (!res.ok) {
    throw new Error(`Daily plan generation API returned HTTP ${res.status}`);
  }

  return await res.json();
}

export async function fetchPollutantMap(
  cityId: string,
  pollutant: string = 'pm25',
  signal?: AbortSignal
): Promise<PollutantMapResponse> {
  const url = new URL(`${API_BASE_URL}/api/v1/map/pollutants`);
  url.searchParams.set('city', cityId);
  url.searchParams.set('pollutant', pollutant);

  const res = await fetchWithCancel(url.toString(), { cache: 'no-store' }, signal);

  if (!res.ok) {
    throw new Error(`Pollutant map API returned HTTP ${res.status}`);
  }

  return await res.json();
}

export async function fetchAirWindow(
  cityId: string,
  activity: string = 'general_outdoor',
  duration?: number,
  isVulnerable?: boolean,
  signal?: AbortSignal
): Promise<AirWindowResponse> {
  const url = new URL(`${API_BASE_URL}/api/v1/air-window`);
  url.searchParams.set('city', cityId);
  url.searchParams.set('activity', activity);
  if (duration) {
    url.searchParams.set('duration', duration.toString());
  }
  if (isVulnerable) {
    url.searchParams.set('is_vulnerable', 'true');
  }

  const res = await fetchWithCancel(url.toString(), { cache: 'no-store' }, signal);

  if (!res.ok) {
    throw new Error(`Air window API returned HTTP ${res.status}`);
  }

  return await res.json();
}
