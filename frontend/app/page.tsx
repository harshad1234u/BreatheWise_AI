'use client';

import React, { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { Navbar } from '@/components/Navbar';
import { CitySelector } from '@/components/CitySelector';
import { AirQualityHero } from '@/components/AirQualityHero';
import { ProvenanceBanner } from '@/components/ProvenanceBanner';
import { PollutantGrid } from '@/components/PollutantGrid';
import { HealthGuidance } from '@/components/HealthGuidance';
import { ForecastWindow } from '@/components/ForecastWindow';
import { ProfileSelector } from '@/components/ProfileSelector';
import { DailyPlanView } from '@/components/DailyPlanView';
import { fetchAirQuality, fetchCities, fetchCityCatalogMeta, generateDailyPlan, isAbortError } from '@/lib/api';
import { CityCatalogMetadata, CityMetadata, NormalizedAirObservation } from '@/types/air-quality';
import { DailyPlanResponse, HouseholdProfile } from '@/types/plan';
import { RefreshCw, AlertCircle, Shield } from 'lucide-react';

const PollutantMap = dynamic(
  () => import('@/components/PollutantMap').then((mod) => mod.PollutantMap),
  {
    ssr: false,
    loading: () => (
      <div className="h-96 rounded-2xl bg-gray-900 border border-gray-800 animate-pulse motion-reduce:animate-none flex items-center justify-center text-gray-300 text-sm">
        Loading metropolitan monitoring network...
      </div>
    ),
  }
);

const DEFAULT_PROFILE: HouseholdProfile = {
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
  activity_preferences: ['School drop-off', 'Desk work', 'Home cooking'],
};

export default function DashboardPage() {
  const [cities, setCities] = useState<CityMetadata[]>([]);
  const [catalogMeta, setCatalogMeta] = useState<CityCatalogMetadata | null>(null);
  const [selectedCityId, setSelectedCityId] = useState<string>('delhi');
  const [observation, setObservation] = useState<NormalizedAirObservation | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Day 2 Intelligence State
  const [profile, setProfile] = useState<HouseholdProfile>(DEFAULT_PROFILE);
  const [dailyPlan, setDailyPlan] = useState<DailyPlanResponse | null>(null);
  const [planLoading, setPlanLoading] = useState<boolean>(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [selectedMapPollutant, setSelectedMapPollutant] = useState<string>('pm25');

  const refreshAbortRef = useRef<AbortController | null>(null);
  const planAbortRef = useRef<AbortController | null>(null);

  const selectedCityObj = cities.find((c) => c.id === selectedCityId);
  const selectedCityName = selectedCityObj?.name || 'Delhi NCR';

  // Load initial city list & stored profile
  useEffect(() => {
    const controller = new AbortController();
    async function loadInitial() {
      try {
        const [cityList, meta] = await Promise.all([
          fetchCities(undefined, controller.signal),
          fetchCityCatalogMeta(controller.signal),
        ]);
        if (!controller.signal.aborted) {
          setCities(cityList);
          setCatalogMeta(meta);
        }
      } catch (err: unknown) {
        if (controller.signal.aborted || isAbortError(err)) return;
      }

      // Check localStorage for saved profile (keeping location decoupled from persona)
      try {
        const saved = localStorage.getItem('breathewise_guest_profile');
        if (saved && !controller.signal.aborted) {
          const parsed = JSON.parse(saved) as HouseholdProfile;
          setProfile(parsed);
        }
      } catch {}
    }
    loadInitial();
    return () => {
      controller.abort();
      refreshAbortRef.current?.abort();
      planAbortRef.current?.abort();
    };
  }, []);

  // Sync profile location when user switches city, preserving chosen persona and map pollutant
  const handleSelectCity = (cityId: string) => {
    if (cityId === selectedCityId) return;
    refreshAbortRef.current?.abort();
    planAbortRef.current?.abort();
    setSelectedCityId(cityId);
    setObservation(null);
    setError(null);
    setDailyPlan(null);
    setPlanError(null);
    setPlanLoading(false);
    setProfile((prev) => ({ ...prev, city: cityId }));
  };

  // Fetch air quality whenever selected city changes
  useEffect(() => {
    if (!selectedCityId) return;

    let isMounted = true;
    refreshAbortRef.current?.abort();
    const controller = new AbortController();

    async function loadAirData() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchAirQuality(selectedCityId, undefined, controller.signal);
        if (isMounted && !controller.signal.aborted) {
          setObservation(data);
        }
      } catch (err: unknown) {
        if (controller.signal.aborted || isAbortError(err)) {
          return;
        }
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Unable to connect to air quality telemetry services.');
        }
      } finally {
        if (isMounted && !controller.signal.aborted) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    }

    loadAirData();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [selectedCityId]);

  // Generate or regenerate daily plan
  const handleGeneratePlan = async () => {
    if (!selectedCityId) return;
    planAbortRef.current?.abort();
    const controller = new AbortController();
    planAbortRef.current = controller;
    setPlanLoading(true);
    setPlanError(null);
    try {
      const plan = await generateDailyPlan(selectedCityId, profile, undefined, controller.signal);
      if (!controller.signal.aborted) {
        setDailyPlan(plan);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted || isAbortError(err)) return;
      setPlanError(err instanceof Error ? err.message : 'Failed to synthesize daily routine plan.');
    } finally {
      if (!controller.signal.aborted) {
        setPlanLoading(false);
      }
    }
  };

  const handleRefresh = async () => {
    if (!selectedCityId || loading || refreshing) return;
    refreshAbortRef.current?.abort();
    const controller = new AbortController();
    refreshAbortRef.current = controller;
    setRefreshing(true);
    try {
      const data = await fetchAirQuality(selectedCityId, undefined, controller.signal);
      if (controller.signal.aborted) return;
      setObservation(data);
      setError(null);
      // If plan already exists, refresh the plan with fresh data
      if (dailyPlan) {
        const updatedPlan = await generateDailyPlan(selectedCityId, profile, undefined, controller.signal);
        if (!controller.signal.aborted) {
          setDailyPlan(updatedPlan);
        }
      }
    } catch (err: unknown) {
      if (controller.signal.aborted || isAbortError(err)) return;
      setError(err instanceof Error ? err.message : 'Failed to refresh telemetry.');
    } finally {
      if (!controller.signal.aborted) {
        setRefreshing(false);
      }
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Page-level semantic heading across loading, error, unavailable, and live states */}
        <section aria-labelledby="dashboard-page-title" className="space-y-1">
          <h1
            id="dashboard-page-title"
            className="text-xl sm:text-2xl font-extrabold tracking-tight text-slate-900 dark:text-white"
          >
            {selectedCityName} Air Quality &amp; Exposure Dashboard
          </h1>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            {loading && !observation
              ? `Loading environmental telemetry for ${selectedCityName}...`
              : error && !observation
              ? `Telemetry connection issue for ${selectedCityName}.`
              : !observation
              ? `Air quality telemetry is currently unavailable for ${selectedCityName}.`
              : 'Live telemetry provenance, hourly exposure forecast, spatial monitoring, and household safety planning.'}
          </p>
        </section>

        {/* City Selector Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="flex-1">
            <CitySelector
              cities={cities}
              catalogMeta={catalogMeta}
              selectedCityId={selectedCityId}
              onSelectCity={handleSelectCity}
              isLoading={loading || refreshing}
            />
          </div>

          <button
            type="button"
            onClick={handleRefresh}
            disabled={loading || refreshing}
            aria-label="Refresh latest telemetry"
            className="flex items-center justify-center gap-2 px-4 py-3 sm:py-0 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-300 transition shadow-sm cursor-pointer disabled:opacity-50"
            title="Refresh latest telemetry"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-teal-600' : ''}`} />
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>

        {/* Error Notification */}
        {error && (
          <div
            role="alert"
            aria-live="assertive"
            className="p-4 rounded-xl border border-rose-300 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/50 text-rose-800 dark:text-rose-200 text-xs flex items-center justify-between gap-3"
          >
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{error}</span>
            </div>
            <button
              type="button"
              onClick={handleRefresh}
              className="underline font-bold hover:text-rose-900 cursor-pointer"
            >
              Retry
            </button>
          </div>
        )}

        {/* Loading Skeleton */}
        {loading && !observation && (
          <div className="space-y-6 animate-pulse motion-reduce:animate-none" aria-live="polite" aria-busy="true">
            <p className="text-xs font-medium text-teal-700 dark:text-teal-300">
              Loading telemetry for {selectedCityName}...
            </p>
            <div className="h-44 rounded-2xl bg-slate-200 dark:bg-slate-800" />
            <div className="h-20 rounded-xl bg-slate-200 dark:bg-slate-800" />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {[...Array(8)].map((_, i) => (
                <div key={i} className="h-28 rounded-xl bg-slate-200 dark:bg-slate-800" />
              ))}
            </div>
          </div>
        )}

        {/* Live Observation Dashboard */}
        {observation && (
          <div className="space-y-6">
            <AirQualityHero observation={observation} />
            <ProvenanceBanner observation={observation} />
            <PollutantGrid observation={observation} />
            <ForecastWindow
              cityId={selectedCityId}
              cityName={selectedCityName}
              isVulnerable={profile.has_respiratory_sensitivity || profile.has_cardiovascular_sensitivity}
            />
            <PollutantMap
              cityId={selectedCityId}
              cityName={selectedCityName}
              selectedPollutant={selectedMapPollutant}
              onSelectPollutant={setSelectedMapPollutant}
            />
            <HealthGuidance category={observation.index_category} />

            {/* Day 2: Intelligence & Household Profile Layer */}
            <ProfileSelector
              currentProfile={profile}
              selectedCityName={selectedCityName}
              onProfileChange={(p) => setProfile({ ...p, city: selectedCityId })}
              onGeneratePlan={handleGeneratePlan}
              isLoading={planLoading}
            />

            {/* Plan Error Notice */}
            {planError && (
              <div
                role="alert"
                aria-live="assertive"
                className="p-4 rounded-xl border border-rose-300 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/50 text-rose-800 dark:text-rose-200 text-xs flex items-center justify-between"
              >
                <span>{planError}</span>
                <button
                  type="button"
                  onClick={handleGeneratePlan}
                  className="underline font-bold"
                >
                  Retry Synthesis
                </button>
              </div>
            )}

            {/* Generated Daily Plan View */}
            {dailyPlan && <DailyPlanView plan={dailyPlan} />}
          </div>
        )}
      </main>

      {/* Footer with Scientific & Public-Health Disclaimers */}
      <footer className="border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 mt-12 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-xs text-slate-500 dark:text-slate-400 space-y-2">
          <div className="flex items-center justify-center gap-1.5 font-semibold text-slate-700 dark:text-slate-300">
            <Shield className="w-4 h-4 text-teal-600" />
            <span>BreatheWise AI • Public Health & Environmental Information System</span>
          </div>
          <p className="max-w-3xl mx-auto leading-relaxed">
            Data provided for advisory lifestyle exposure reduction. Calculations follow official Central Pollution Control Board (CPCB) breakpoint methodology. BreatheWise AI is not a medical device and does not substitute clinical diagnosis or official public emergency alerts.
          </p>
          <p className="pt-2 text-[11px] text-slate-600 dark:text-slate-400">
            PromptWars Virtual Challenge 6 • Urban Air Quality Assistant
          </p>
        </div>
      </footer>
    </div>
  );
}
