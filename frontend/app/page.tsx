'use client';

import React, { useEffect, useState } from 'react';
import { Navbar } from '@/components/Navbar';
import { CitySelector } from '@/components/CitySelector';
import { AirQualityHero } from '@/components/AirQualityHero';
import { ProvenanceBanner } from '@/components/ProvenanceBanner';
import { PollutantGrid } from '@/components/PollutantGrid';
import { HealthGuidance } from '@/components/HealthGuidance';
import { fetchAirQuality, fetchCities } from '@/lib/api';
import { CityMetadata, NormalizedAirObservation } from '@/types/air-quality';
import { RefreshCw, AlertCircle, Shield } from 'lucide-react';

export default function DashboardPage() {
  const [cities, setCities] = useState<CityMetadata[]>([]);
  const [selectedCityId, setSelectedCityId] = useState<string>('delhi');
  const [observation, setObservation] = useState<NormalizedAirObservation | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Load initial city list
  useEffect(() => {
    async function loadCities() {
      const cityList = await fetchCities();
      setCities(cityList);
      if (cityList.length > 0 && !selectedCityId) {
        setSelectedCityId(cityList[0].id);
      }
    }
    loadCities();
  }, []);

  // Fetch air quality whenever selected city changes
  useEffect(() => {
    if (!selectedCityId) return;

    let isMounted = true;

    async function loadAirData() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchAirQuality(selectedCityId);
        if (isMounted) {
          setObservation(data);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err?.message || 'Unable to connect to air quality telemetry services.');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    }

    loadAirData();

    return () => {
      isMounted = false;
    };
  }, [selectedCityId]);

  const handleRefresh = async () => {
    if (!selectedCityId || loading || refreshing) return;
    setRefreshing(true);
    try {
      const data = await fetchAirQuality(selectedCityId);
      setObservation(data);
      setError(null);
    } catch (err: any) {
      setError(err?.message || 'Failed to refresh telemetry.');
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* City Selector Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="flex-1">
            <CitySelector
              cities={cities}
              selectedCityId={selectedCityId}
              onSelectCity={(id) => setSelectedCityId(id)}
              isLoading={loading || refreshing}
            />
          </div>

          <button
            onClick={handleRefresh}
            disabled={loading || refreshing}
            className="flex items-center justify-center gap-2 px-4 py-3 sm:py-0 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-300 transition shadow-sm cursor-pointer disabled:opacity-50"
            title="Refresh latest telemetry"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-teal-600' : ''}`} />
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="p-4 rounded-xl border border-rose-300 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/50 text-rose-800 dark:text-rose-200 text-xs flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{error}</span>
            </div>
            <button
              onClick={handleRefresh}
              className="underline font-bold hover:text-rose-900 cursor-pointer"
            >
              Retry
            </button>
          </div>
        )}

        {/* Loading Skeleton */}
        {loading && !observation && (
          <div className="space-y-6 animate-pulse">
            <div className="h-44 rounded-2xl bg-slate-200 dark:bg-slate-800" />
            <div className="h-20 rounded-xl bg-slate-200 dark:bg-slate-800" />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {[...Array(6)].map((_, i) => (
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
            <HealthGuidance category={observation.index_category} />
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
          <p className="pt-2 text-[11px] text-slate-400">
            PromptWars Virtual Challenge 6 • Day 1 Verified Baseline
          </p>
        </div>
      </footer>
    </div>
  );
}
