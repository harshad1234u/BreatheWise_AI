import { CityMetadata, NormalizedAirObservation } from '@/types/air-quality';
import { DailyPlanResponse, HouseholdProfile } from '@/types/plan';
import { PollutantMapResponse } from '@/types/map';
import { AirWindowResponse } from '@/types/air-window';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchCities(): Promise<CityMetadata[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/cities`, {
      cache: 'no-store',
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch cities: ${res.statusText}`);
    }
    return await res.json();
  } catch (error) {
    console.error('Error fetching cities:', error);
    // Fallback default city list in case backend is warming up
    return [
      { id: 'delhi', name: 'Delhi NCR', state: 'Delhi', latitude: 28.6139, longitude: 77.2090, waqi_keyword: 'delhi' },
      { id: 'mumbai', name: 'Mumbai', state: 'Maharashtra', latitude: 19.0760, longitude: 72.8777, waqi_keyword: 'mumbai' },
      { id: 'bengaluru', name: 'Bengaluru', state: 'Karnataka', latitude: 12.9716, longitude: 77.5946, waqi_keyword: 'bangalore' },
      { id: 'hyderabad', name: 'Hyderabad', state: 'Telangana', latitude: 17.3850, longitude: 78.4867, waqi_keyword: 'hyderabad' },
      { id: 'kolkata', name: 'Kolkata', state: 'West Bengal', latitude: 22.5726, longitude: 88.3639, waqi_keyword: 'kolkata' },
      { id: 'chennai', name: 'Chennai', state: 'Tamil Nadu', latitude: 13.0827, longitude: 80.2707, waqi_keyword: 'chennai' },
    ];
  }
}

export async function fetchAirQuality(
  cityId: string,
  stationId?: string
): Promise<NormalizedAirObservation> {
  const url = new URL(`${API_BASE_URL}/api/v1/air-quality`);
  url.searchParams.set('city', cityId);
  if (stationId) {
    url.searchParams.set('station_id', stationId);
  }

  const res = await fetch(url.toString(), {
    cache: 'no-store',
  });

  if (!res.ok) {
    throw new Error(`Air quality API returned HTTP ${res.status}`);
  }

  return await res.json();
}

export async function generateDailyPlan(
  cityId: string,
  profile: HouseholdProfile,
  stationId?: string
): Promise<DailyPlanResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/plan/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      city: cityId,
      station_id: stationId,
      profile: profile,
    }),
  });

  if (!res.ok) {
    throw new Error(`Daily plan generation API returned HTTP ${res.status}`);
  }

  return await res.json();
}

export async function fetchPollutantMap(
  cityId: string,
  pollutant: string = 'pm25'
): Promise<PollutantMapResponse> {
  const url = new URL(`${API_BASE_URL}/api/v1/map/pollutants`);
  url.searchParams.set('city', cityId);
  url.searchParams.set('pollutant', pollutant);

  const res = await fetch(url.toString(), {
    cache: 'no-store',
  });

  if (!res.ok) {
    throw new Error(`Pollutant map API returned HTTP ${res.status}`);
  }

  return await res.json();
}

export async function fetchAirWindow(
  cityId: string,
  activity: string = 'general_outdoor',
  duration?: number,
  isVulnerable?: boolean
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

  const res = await fetch(url.toString(), {
    cache: 'no-store',
  });

  if (!res.ok) {
    throw new Error(`Air window API returned HTTP ${res.status}`);
  }

  return await res.json();
}
