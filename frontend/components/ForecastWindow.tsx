'use client';

import React, { useState, useEffect } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import {
  Clock,
  Activity,
  AlertTriangle,
  Info,
  CheckCircle2,
  TrendingDown,
  TrendingUp,
  Wind,
} from 'lucide-react';
import { AirWindowResponse, HourlyPollutantPoint } from '@/types/air-window';
import { fetchAirWindow } from '@/lib/api';

interface ForecastWindowProps {
  cityId: string;
  cityName: string;
  isVulnerable?: boolean;
}

const ACTIVITIES = [
  { id: 'running', label: 'Running / Outdoor Cardio', duration: 1 },
  { id: 'walking', label: 'Walking / School Commute', duration: 1 },
  { id: 'cycling', label: 'Cycling', duration: 1 },
  { id: 'errand', label: 'Outdoor Errand / Market', duration: 1 },
  { id: 'ventilation', label: 'Home Ventilation / Window Airing', duration: 1 },
];

export function ForecastWindow({ cityId, cityName, isVulnerable = false }: ForecastWindowProps) {
  const [selectedActivity, setSelectedActivity] = useState<string>('running');
  const [data, setData] = useState<AirWindowResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showBreakdown, setShowBreakdown] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;

    async function loadForecast() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetchAirWindow(cityId, selectedActivity, 1, isVulnerable);
        if (isMounted) {
          setData(res);
        }
      } catch (err: unknown) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Could not load atmospheric forecast data.');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadForecast();

    return () => {
      isMounted = false;
    };
  }, [cityId, selectedActivity, isVulnerable]);

  const bestWindow = data?.best_window;
  const peakWindow = data?.peak_pollution_window;
  const forecastPoints = data?.hourly_forecast?.slice(0, 24) || [];

  // Determine color styling for CPCB score bands
  const getBandBadgeClass = (score: number) => {
    if (score <= 50) return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20';
    if (score <= 100) return 'bg-lime-500/10 text-lime-600 dark:text-lime-400 border-lime-500/20';
    if (score <= 200) return 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20';
    if (score <= 300) return 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20';
    if (score <= 400) return 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20';
    return 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20';
  };

  return (
    <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-teal-500/10 text-teal-600 dark:text-teal-400">
              <Clock className="w-4 h-4" />
            </span>
            <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
              Best Air Window Engine — Hourly Forecast
            </h2>
            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
              Model Forecast
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Comparative diurnal exposure analysis across 6 criteria pollutants ({cityName}).
          </p>
        </div>

        {/* Activity Selector Pills */}
        <div
          className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0 scrollbar-none"
          role="group"
          aria-label="Select outdoor activity for forecast"
        >
          {ACTIVITIES.map((act) => (
            <button
              key={act.id}
              type="button"
              aria-pressed={selectedActivity === act.id}
              onClick={() => setSelectedActivity(act.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition cursor-pointer ${
                selectedActivity === act.id
                  ? 'bg-teal-600 text-white shadow-sm'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              {act.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="p-5 space-y-6">
        {loading && (
          <div className="py-12 flex flex-col items-center justify-center space-y-3" aria-live="polite" aria-busy="true">
            <div className="w-8 h-8 rounded-full border-2 border-teal-600 border-t-transparent animate-spin" />
            <span className="text-xs text-slate-500">Calculating diurnal multi-pollutant trajectory...</span>
          </div>
        )}

        {error && (
          <div
            role="alert"
            aria-live="assertive"
            className="p-4 rounded-xl border border-rose-300 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/50 text-rose-800 dark:text-rose-200 text-xs flex items-center gap-2"
          >
            <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && data && (
          <>
            {/* Top Cards: Best Window & Peak Window Side-by-Side */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Lowest Forecast Period Card */}
              {bestWindow && (
                <div className="p-4 rounded-xl border border-emerald-500/20 bg-emerald-50/30 dark:bg-emerald-950/20 space-y-3 relative overflow-hidden">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="p-1 rounded-md bg-emerald-500/20 text-emerald-600 dark:text-emerald-400">
                        <TrendingDown className="w-4 h-4" />
                      </span>
                      <span className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-300">
                        {bestWindow.score_label}
                      </span>
                    </div>
                    <span
                      className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${getBandBadgeClass(
                        bestWindow.average_comparative_score
                      )}`}
                    >
                      Score: {bestWindow.average_comparative_score}
                    </span>
                  </div>

                  <div className="flex items-baseline gap-2">
                    <span className="text-2xl font-black tracking-tight text-slate-900 dark:text-slate-100">
                      {bestWindow.start_time} - {bestWindow.end_time}
                    </span>
                    <span className="text-xs text-slate-500 font-medium">({bestWindow.duration_hours} hr window)</span>
                  </div>

                  <div className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed bg-white/60 dark:bg-slate-900/60 p-2.5 rounded-lg border border-emerald-500/10">
                    <div className="font-semibold mb-1 flex items-center gap-1.5 text-slate-900 dark:text-slate-100">
                      <Activity className="w-3.5 h-3.5 text-emerald-600" />
                      Activity Suitability:
                    </div>
                    <p>{bestWindow.activity_suitability}</p>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500 pt-1">
                    <span>
                      Dominant Pollutant:{' '}
                      <strong className="uppercase text-slate-700 dark:text-slate-300">
                        {bestWindow.dominant_pollutant}
                      </strong>
                    </span>
                    <span>•</span>
                    <span>
                      Strenuous Cardio Allowed:{' '}
                      <strong className={bestWindow.strenuous_outdoor_allowed ? 'text-emerald-600' : 'text-rose-600'}>
                        {bestWindow.strenuous_outdoor_allowed ? 'Acceptable' : 'Restricted (Shift Indoors)'}
                      </strong>
                    </span>
                  </div>
                </div>
              )}

              {/* Peak Forecast Pollution Period Card */}
              {peakWindow && (
                <div className="p-4 rounded-xl border border-rose-500/20 bg-rose-50/30 dark:bg-rose-950/20 space-y-3 relative overflow-hidden">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="p-1 rounded-md bg-rose-500/20 text-rose-600 dark:text-rose-400">
                        <TrendingUp className="w-4 h-4" />
                      </span>
                      <span className="text-xs font-bold uppercase tracking-wider text-rose-700 dark:text-rose-300">
                        {peakWindow.score_label}
                      </span>
                    </div>
                    <span
                      className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${getBandBadgeClass(
                        peakWindow.average_comparative_score
                      )}`}
                    >
                      Peak Score: {peakWindow.average_comparative_score}
                    </span>
                  </div>

                  <div className="flex items-baseline gap-2">
                    <span className="text-2xl font-black tracking-tight text-slate-900 dark:text-slate-100">
                      {peakWindow.start_time} - {peakWindow.end_time}
                    </span>
                    <span className="text-xs text-rose-600 dark:text-rose-400 font-medium">Avoid Outdoor Workouts</span>
                  </div>

                  <div className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed bg-white/60 dark:bg-slate-900/60 p-2.5 rounded-lg border border-rose-500/10">
                    <div className="font-semibold mb-1 flex items-center gap-1.5 text-slate-900 dark:text-slate-100">
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                      Accumulation Advisory:
                    </div>
                    <p>{peakWindow.activity_suitability}</p>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500 pt-1">
                    <span>
                      Primary Driver:{' '}
                      <strong className="uppercase text-slate-700 dark:text-slate-300">
                        {peakWindow.dominant_pollutant}
                      </strong>
                    </span>
                    <span>•</span>
                    <span className="text-rose-600 dark:text-rose-400 font-medium">
                      Inversion / Traffic Peak Period
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Alternative Windows (if any) */}
            {data.alternative_windows && data.alternative_windows.length > 0 && (
              <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex flex-wrap items-center gap-3 text-xs">
                <span className="font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-teal-600" />
                  Alternative Windows:
                </span>
                {data.alternative_windows.map((alt, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-2 px-3 py-1 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300"
                  >
                    <span className="font-bold">
                      {alt.start_time} - {alt.end_time}
                    </span>
                    <span className="text-[11px] text-slate-500">(Score: {alt.average_comparative_score})</span>
                    <span className="text-[10px] uppercase font-bold text-teal-600 dark:text-teal-400">
                      {alt.score_label}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Interactive Forecast Chart */}
            <div className="space-y-3 pt-2">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5 text-teal-600" />
                    24-Hour Diurnal Pollution Exposure Curve
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Comparative score E(t) = max sub-index across available criteria pollutants for each hour.
                  </p>
                </div>

                <button
                  type="button"
                  aria-expanded={showBreakdown}
                  onClick={() => setShowBreakdown(!showBreakdown)}
                  className="text-xs font-medium text-teal-600 dark:text-teal-400 hover:underline flex items-center gap-1 cursor-pointer"
                >
                  {showBreakdown ? 'Hide individual pollutant traces' : 'Show PM2.5, PM10 & O3 traces'}
                </button>
              </div>

              <div className="h-64 w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={forecastPoints} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#0d9488" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#0d9488" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.2} />
                    <XAxis
                      dataKey="hour_label"
                      stroke="#94a3b8"
                      fontSize={11}
                      tickLine={false}
                      interval={2}
                    />
                    <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} domain={[0, 'auto']} />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const pt = payload[0].payload as HourlyPollutantPoint;
                          return (
                            <div className="rounded-lg border border-slate-700 bg-slate-900 p-2.5 text-xs text-white shadow-xl space-y-1">
                              <div className="font-bold text-teal-400 flex items-center justify-between gap-4">
                                <span>Hour: {pt.hour_label}</span>
                                <span className="uppercase text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                                  {pt.category_label}
                                </span>
                              </div>
                              <div className="text-slate-300">
                                Comparative Score: <strong className="text-white">{pt.comparative_score}</strong>
                              </div>
                              <div className="text-[11px] text-slate-400">
                                Dominant: <span className="uppercase font-semibold text-teal-300">{pt.dominant_pollutant}</span>
                              </div>
                              {pt.pm25 !== null && (
                                <div className="text-[11px] text-slate-400">
                                  PM2.5: <span className="text-slate-200">{pt.pm25} µg/m³</span>
                                </div>
                              )}
                              {pt.pm10 !== null && (
                                <div className="text-[11px] text-slate-400">
                                  PM10: <span className="text-slate-200">{pt.pm10} µg/m³</span>
                                </div>
                              )}
                              {pt.o3 !== null && (
                                <div className="text-[11px] text-slate-400">
                                  O3: <span className="text-slate-200">{pt.o3} µg/m³</span>
                                </div>
                              )}
                              {pt.wind_speed !== null && (
                                <div className="text-[11px] text-slate-400 flex items-center gap-1">
                                  <Wind className="w-3 h-3 text-sky-400" />
                                  <span>Wind: {pt.wind_speed} km/h</span>
                                </div>
                              )}
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="comparative_score"
                      stroke="#0d9488"
                      strokeWidth={2.5}
                      fillOpacity={1}
                      fill="url(#scoreGradient)"
                      name="Comparative Score"
                    />
                    {showBreakdown && (
                      <>
                        <Line
                          type="monotone"
                          dataKey="pm25"
                          stroke="#ef4444"
                          strokeWidth={1.5}
                          dot={false}
                          name="PM2.5 (µg/m³)"
                        />
                        <Line
                          type="monotone"
                          dataKey="pm10"
                          stroke="#f59e0b"
                          strokeWidth={1.5}
                          dot={false}
                          name="PM10 (µg/m³)"
                        />
                        <Line
                          type="monotone"
                          dataKey="o3"
                          stroke="#06b6d4"
                          strokeWidth={1.5}
                          dot={false}
                          name="O3 (µg/m³)"
                        />
                      </>
                    )}
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Scientific & Public Health Model Disclaimer */}
            <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/60 text-xs text-slate-500 dark:text-slate-400 flex items-start gap-2.5">
              <Info className="w-4 h-4 text-teal-600 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="font-semibold text-slate-700 dark:text-slate-300">
                  Model Provenance & Public Health Disclosure:
                </p>
                <p className="leading-relaxed">{data.disclaimer}</p>
                <p className="text-[11px] text-slate-400">
                  Data Provider: {data.data_provider} • Confidence: {data.confidence.toUpperCase()}
                </p>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
