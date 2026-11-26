'use client';

import React, { useEffect, useRef, useState } from 'react';
import type * as LeafletTypes from 'leaflet';
import {
  MapPin,
  Layers,
  Info,
  AlertTriangle,
  RefreshCw,
  Compass,
  CheckCircle2,
} from 'lucide-react';
import { fetchPollutantMap } from '@/lib/api';
import { PollutantMapResponse, StationMapPoint } from '@/types/map';

import 'leaflet/dist/leaflet.css';

interface PollutantMapProps {
  cityId: string;
  cityName: string;
}

const POLLUTANTS = [
  { id: 'pm25', label: 'PM2.5', unit: 'µg/m³', fullName: 'Fine Particulates' },
  { id: 'pm10', label: 'PM10', unit: 'µg/m³', fullName: 'Coarse Particulates' },
  { id: 'no2', label: 'NO₂', unit: 'µg/m³', fullName: 'Nitrogen Dioxide' },
  { id: 'o3', label: 'O₃', unit: 'µg/m³', fullName: 'Ground Ozone' },
  { id: 'so2', label: 'SO₂', unit: 'µg/m³', fullName: 'Sulfur Dioxide' },
  { id: 'co', label: 'CO', unit: 'mg/m³', fullName: 'Carbon Monoxide' },
  { id: 'nh3', label: 'NH₃', unit: 'µg/m³', fullName: 'Ammonia' },
  { id: 'pb', label: 'Pb', unit: 'µg/m³', fullName: 'Lead' },
];

function getStationDisplayCategory(station: StationMapPoint): string {
  if (station.measurement_type === 'provider_index') {
    return station.provider_index_category || 'Unavailable';
  }
  return station.sub_index_category;
}

function getCategoryColor(category: string): string {
  switch (category) {
    case 'Good':
      return '#10B981';
    case 'Satisfactory':
      return '#84CC16';
    case 'Moderate':
      return '#F59E0B';
    case 'Moderate (Sensitive)':
    case 'Poor':
      return '#F97316';
    case 'Very Poor':
      return '#EF4444';
    case 'Severe':
      return '#991B1B';
    default:
      return '#6B7280';
  }
}

function getCategoryBadgeClass(category: string): string {
  switch (category) {
    case 'Good':
      return 'bg-emerald-950/80 text-emerald-300 border-emerald-700/60';
    case 'Satisfactory':
      return 'bg-lime-950/80 text-lime-300 border-lime-700/60';
    case 'Moderate':
      return 'bg-amber-950/80 text-amber-300 border-amber-700/60';
    case 'Moderate (Sensitive)':
    case 'Poor':
      return 'bg-orange-950/80 text-orange-300 border-orange-700/60';
    case 'Very Poor':
      return 'bg-red-950/80 text-red-300 border-red-700/60';
    case 'Severe':
      return 'bg-rose-950/90 text-rose-200 border-rose-800';
    default:
      return 'bg-gray-800 text-gray-400 border-gray-700';
  }
}

function formatMeasurementLabel(station: StationMapPoint, unit: string): string {
  if (station.measurement_type === 'provider_index' && station.provider_index !== null) {
    return `WAQI Index: ${station.provider_index}`;
  }
  if (
    (station.measurement_type === 'raw_concentration' || station.measurement_type === 'model_estimate') &&
    station.concentration !== null
  ) {
    return `${station.concentration} ${unit}`;
  }
  return 'Unavailable';
}

function getMeasurementTypeDescriptor(station: StationMapPoint): string {
  switch (station.measurement_type) {
    case 'provider_index':
      return 'Provider index — not raw concentration';
    case 'raw_concentration':
      return 'Raw station concentration';
    case 'cpcb_sub_index':
      return 'CPCB concentration sub-index';
    case 'model_estimate':
      return 'Atmospheric model estimate';
    default:
      return 'Unavailable';
  }
}

export const PollutantMap: React.FC<PollutantMapProps> = ({ cityId, cityName }) => {
  const [selectedPollutant, setSelectedPollutant] = useState<string>('pm25');
  const [mapData, setMapData] = useState<PollutantMapResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStation, setSelectedStation] = useState<StationMapPoint | null>(null);

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<LeafletTypes.Map | null>(null);
  const markersLayerRef = useRef<LeafletTypes.FeatureGroup | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      setLoading(true);
      setError(null);
      setSelectedStation(null);
      try {
        const data = await fetchPollutantMap(cityId, selectedPollutant);
        if (isMounted) {
          setMapData(data);
          if (data.stations.length > 0) {
            setSelectedStation(data.stations[0]);
          }
        }
      } catch (err: unknown) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Failed to fetch regional pollutant telemetry');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadData();
    return () => {
      isMounted = false;
    };
  }, [cityId, selectedPollutant]);

  useEffect(() => {
    let isCancelled = false;

    async function renderMap() {
      if (!mapContainerRef.current) return;

      let L: typeof import('leaflet');
      try {
        const mod = await import('leaflet');
        L = mod.default ?? mod;
      } catch (err: unknown) {
        console.error('Leaflet load error:', err);
        return;
      }

      if (isCancelled || !mapContainerRef.current) return;

      if (!mapInstanceRef.current) {
        const map = L.map(mapContainerRef.current, {
          center: [mapData?.city_center_lat || 28.6139, mapData?.city_center_lng || 77.2090],
          zoom: 11,
          zoomControl: true,
          scrollWheelZoom: false,
        });

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          subdomains: ['a', 'b', 'c'],
          maxZoom: 18,
          className: 'dark-tiles-filter',
        }).addTo(map);

        const markersGroup = L.featureGroup().addTo(map);
        markersLayerRef.current = markersGroup;
        mapInstanceRef.current = map;
      }

      const map = mapInstanceRef.current;
      const markersGroup = markersLayerRef.current;

      if (!map || !markersGroup || !mapData) return;

      markersGroup.clearLayers();
      map.setView([mapData.city_center_lat, mapData.city_center_lng], 11);

      if (mapData.stations.length === 0) {
        return;
      }

      mapData.stations.forEach((station) => {
        const displayCategory = getStationDisplayCategory(station);
        const color = getCategoryColor(displayCategory);
        const isReporting = station.measurement_type !== 'unavailable';

        const marker = L.circleMarker([station.latitude, station.longitude], {
          radius: isReporting ? 9 : 6,
          fillColor: color,
          color: '#FFFFFF',
          weight: 1.5,
          opacity: 0.9,
          fillOpacity: 0.85,
        });

        const obsDisplay = station.observed_at
          ? new Date(station.observed_at).toLocaleString([], {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })
          : 'Missing timestamp';

        const measurementRow =
          station.measurement_type === 'provider_index' && station.provider_index !== null
            ? `<div style="margin-bottom: 2px;"><strong>WAQI Provider Index:</strong> ${station.provider_index}</div>
               <div style="margin-bottom: 2px;"><strong>Raw Concentration:</strong> <span style="color: #9CA3AF;">Not provided by source</span></div>`
            : station.concentration !== null
            ? `<div style="margin-bottom: 2px;"><strong>Concentration:</strong> ${station.concentration} ${mapData.unit}</div>`
            : `<div style="margin-bottom: 2px;"><strong>Measurement:</strong> <span style="color: #9CA3AF;">Unavailable</span></div>`;

        const popupContent = `
        <div style="font-family: inherit; font-size: 12px; color: #F3F4F6; background: #111827; padding: 6px; border-radius: 6px; min-width: 210px;">
          <div style="font-weight: 700; margin-bottom: 4px; color: #60A5FA;">${station.station_name}</div>
          ${measurementRow}
          <div style="margin-bottom: 2px;"><strong>Type:</strong> ${getMeasurementTypeDescriptor(station)}</div>
          <div style="margin-bottom: 2px;"><strong>CPCB Sub-Index:</strong> ${
            station.cpcb_sub_index !== null ? Math.round(station.cpcb_sub_index) : 'Unavailable'
          }</div>
          <div style="margin-bottom: 2px;"><strong>Provider:</strong> ${station.data_provider}</div>
          <div style="font-size: 11px; color: #9CA3AF;"><strong>Observed:</strong> ${obsDisplay} (${station.freshness_status})</div>
        </div>
      `;

        marker.bindPopup(popupContent);
        marker.on('click', () => {
          setSelectedStation(station);
        });

        markersGroup.addLayer(marker);
      });

      if (mapData.stations.length > 1) {
        try {
          map.fitBounds(markersGroup.getBounds().pad(0.1));
        } catch {
          map.setView([mapData.city_center_lat, mapData.city_center_lng], 11);
        }
      }
    }

    void renderMap();

    return () => {
      isCancelled = true;
    };
  }, [mapData]);

  const summary = mapData?.summary;
  const isProviderIndexMode = summary?.measurement_mode === 'provider_index';
  const isModelMode = summary?.measurement_mode === 'model_estimate';

  return (
    <section className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6">
      {/* Header and Metas */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-5">
        <div>
          <div className="flex items-center gap-2 text-blue-400 font-semibold text-xs tracking-wider uppercase mb-1">
            <Compass className="w-4 h-4" />
            Metropolitan Spatial Intelligence
          </div>
          <h2 className="text-xl md:text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            Interactive Pollutant Distribution Map
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-blue-950/80 text-blue-400 border border-blue-800/60 font-medium">
              {cityName}
            </span>
          </h2>
          <p className="text-sm text-gray-400 mt-1">
            {isModelMode
              ? `Atmospheric model grid estimate for ${cityName} (no ground monitoring stations reported in range).`
              : isProviderIndexMode
              ? `Monitoring stations around ${cityName} reporting WAQI provider sub-indices (not raw mass concentrations).`
              : `Monitoring station distribution around ${cityName} with explicit measurement provenance.`}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right hidden sm:block">
            <div className="text-xs text-gray-400">Map Base & Source</div>
            <div className="text-xs font-semibold text-gray-200">
              {isModelMode ? 'OpenStreetMap • Open-Meteo CAMS' : 'OpenStreetMap • WAQI Provider Feed'}
            </div>
          </div>
          <button
            type="button"
            aria-label={`Refresh pollutant map telemetry for ${cityName}`}
            onClick={async () => {
              setLoading(true);
              setError(null);
              try {
                const data = await fetchPollutantMap(cityId, selectedPollutant);
                setMapData(data);
                if (data.stations.length > 0) {
                  setSelectedStation(data.stations[0]);
                }
              } catch (err: unknown) {
                setError(err instanceof Error ? err.message : 'Failed to refresh pollutant map telemetry');
              }
              setLoading(false);
            }}
            disabled={loading}
            className="p-2.5 rounded-xl bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white transition-colors border border-gray-700 disabled:opacity-50"
            title="Refresh map telemetry"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Pollutant Selector Pills */}
      <div>
        <span id="pollutant-selector-label" className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2.5">
          Select Criteria Pollutant Parameter:
        </span>
        <div
          className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2"
          role="group"
          aria-labelledby="pollutant-selector-label"
        >
          {POLLUTANTS.map((p) => {
            const isActive = selectedPollutant === p.id;
            return (
              <button
                key={p.id}
                type="button"
                aria-pressed={isActive}
                onClick={() => setSelectedPollutant(p.id)}
                className={`py-2 px-3 rounded-xl text-xs font-semibold transition-all border text-left flex flex-col justify-between ${
                  isActive
                    ? 'bg-blue-600 text-white border-blue-500 shadow-lg shadow-blue-900/30 ring-1 ring-blue-400'
                    : 'bg-gray-800/80 text-gray-300 border-gray-700/80 hover:bg-gray-800 hover:border-gray-600'
                }`}
              >
                <div className="font-bold text-sm">{p.label}</div>
                <div className="text-[10px] opacity-75">{p.unit}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Measurement-Aware Summary KPI Strip */}
      {mapData && summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-gray-950/60 p-4 rounded-xl border border-gray-800/80">
          <div>
            <div className="text-[11px] text-gray-400 uppercase font-medium">
              {isProviderIndexMode
                ? 'Provider-Index Stations'
                : isModelMode
                ? 'Model Grid Points'
                : 'Concentration Stations'}
            </div>
            <div className="text-base font-bold text-white mt-0.5">
              {summary.reporting_stations}{' '}
              <span className="text-xs font-normal text-gray-400">/ {summary.total_stations} Reporting</span>
            </div>
          </div>

          <div>
            <div className="text-[11px] text-gray-400 uppercase font-medium">
              {isProviderIndexMode ? 'Avg WAQI Provider Index' : 'Regional Concentration Avg'}
            </div>
            <div className="text-base font-bold text-white mt-0.5">
              {isProviderIndexMode
                ? summary.avg_provider_index !== null
                  ? `${summary.avg_provider_index} (US-EPA AQI)`
                  : 'Unavailable'
                : summary.avg_concentration !== null
                ? `${summary.avg_concentration} ${mapData.unit}`
                : 'Unavailable'}
            </div>
          </div>

          <div>
            <div className="text-[11px] text-gray-400 uppercase font-medium">
              {isProviderIndexMode ? 'Provider Index Range' : 'Concentration Range'}
            </div>
            <div className="text-base font-bold text-white mt-0.5">
              {isProviderIndexMode
                ? summary.min_provider_index !== null && summary.max_provider_index !== null
                  ? `${summary.min_provider_index} – ${summary.max_provider_index}`
                  : 'Unavailable'
                : summary.min_concentration !== null && summary.max_concentration !== null
                ? `${summary.min_concentration} – ${summary.max_concentration} ${mapData.unit}`
                : 'Unavailable'}
            </div>
          </div>

          <div>
            <div className="text-[11px] text-gray-400 uppercase font-medium">Measurement Semantics</div>
            <div
              className={`text-xs font-semibold mt-1 flex items-center gap-1 ${
                summary.measurement_mode === 'unavailable'
                  ? 'text-amber-400'
                  : isModelMode
                  ? 'text-sky-400'
                  : 'text-emerald-400'
              }`}
            >
              <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
              <span>
                {isProviderIndexMode
                  ? 'WAQI Provider Index (Not µg/m³)'
                  : isModelMode
                  ? 'Model-Derived Estimate (CAMS)'
                  : summary.measurement_mode === 'raw_concentration'
                  ? 'Raw Station Concentration'
                  : 'Measurement Unavailable'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Leaflet Map Canvas */}
      <div className="relative w-full h-[420px] rounded-xl overflow-hidden border border-gray-800 bg-gray-950">
        <div
          ref={mapContainerRef}
          className="w-full h-full z-0"
          role="region"
          aria-label={`Interactive monitoring station map for ${cityName}`}
        />

        {loading && (
          <div
            className="absolute inset-0 bg-gray-950/80 backdrop-blur-sm z-10 flex flex-col items-center justify-center gap-3"
            aria-live="polite"
            aria-busy="true"
          >
            <RefreshCw className="w-7 h-7 text-blue-400 animate-spin" />
            <p className="text-xs text-gray-300 font-medium tracking-wide">
              Loading monitoring station telemetry for {cityName}...
            </p>
          </div>
        )}

        {!loading && error && (
          <div
            role="alert"
            aria-live="assertive"
            className="absolute inset-0 bg-gray-950/90 z-10 flex flex-col items-center justify-center p-6 text-center"
          >
            <AlertTriangle className="w-8 h-8 text-rose-400 mb-2" />
            <h4 className="text-sm font-bold text-gray-100">Unable to Load Pollutant Map</h4>
            <p className="text-xs text-rose-300 mt-1 max-w-md">{error}</p>
          </div>
        )}

        {!loading && !error && mapData && mapData.stations.length === 0 && (
          <div className="absolute inset-0 bg-gray-950/90 z-10 flex flex-col items-center justify-center p-6 text-center">
            <AlertTriangle className="w-8 h-8 text-amber-400 mb-2" />
            <h4 className="text-sm font-bold text-gray-200">No Monitoring Stations Available</h4>
            <p className="text-xs text-gray-400 mt-1 max-w-md">
              Neither ground telemetry nor grid models currently report {selectedPollutant.toUpperCase()} for {cityName}.
              Missing values are preserved as unavailable rather than simulated.
            </p>
          </div>
        )}

        {/* In-Map Legend */}
        <div className="absolute bottom-3 right-3 z-10 bg-gray-900/90 backdrop-blur-md p-2.5 rounded-lg border border-gray-800 text-[11px] shadow-lg max-w-[235px]">
          <div className="font-semibold text-gray-300 mb-1.5 flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-blue-400" />
            {isProviderIndexMode ? 'WAQI US-EPA Index Scale' : 'CPCB Sub-Index Scale'}
          </div>
          <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[10px]">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0" />
              <span className="text-gray-300">Good (0–50)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 shrink-0" />
              <span className="text-gray-300">Moderate (51–150)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-orange-500 shrink-0" />
              <span className="text-gray-300">Poor (151–200)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0" />
              <span className="text-gray-300">Very Poor (201–300)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-red-800 shrink-0" />
              <span className="text-gray-300">Severe (301+)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-gray-500 shrink-0" />
              <span className="text-gray-300">Unavailable</span>
            </div>
          </div>
        </div>
      </div>

      {/* Keyboard-Accessible Station Picker */}
      {mapData && mapData.stations.length > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-gray-950/60 px-4 py-3 rounded-xl border border-gray-800/80">
          <label htmlFor="station-inspector-select" className="text-xs font-semibold text-gray-300">
            Inspect Monitoring Station ({mapData.stations.length} locations):
          </label>
          <select
            id="station-inspector-select"
            value={selectedStation?.station_id || ''}
            onChange={(e) => {
              const found = mapData.stations.find((s) => s.station_id === e.target.value);
              if (found) {
                setSelectedStation(found);
                mapInstanceRef.current?.setView([found.latitude, found.longitude], 13);
              }
            }}
            className="p-2 rounded-lg border border-gray-700 bg-gray-900 text-gray-100 text-xs max-w-md w-full sm:w-auto"
          >
            {mapData.stations.map((s) => (
              <option key={s.station_id} value={s.station_id}>
                {s.station_name} — {formatMeasurementLabel(s, mapData.unit)}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Selected Station Detailed Inspector Card */}
      {selectedStation && (
        <div className="bg-gray-950 p-4 rounded-xl border border-gray-800 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <MapPin className="w-4 h-4 text-blue-400 shrink-0" />
              <h4 className="text-sm font-bold text-white">{selectedStation.station_name}</h4>
              <span
                className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${getCategoryBadgeClass(
                  getStationDisplayCategory(selectedStation)
                )}`}
              >
                {getStationDisplayCategory(selectedStation)}
              </span>
            </div>
            <div className="text-xs text-gray-400 flex flex-wrap items-center gap-x-3 gap-y-1">
              <span>
                Coordinates: {selectedStation.latitude.toFixed(4)}, {selectedStation.longitude.toFixed(4)}
              </span>
              <span>•</span>
              <span>Provider: {selectedStation.data_provider}</span>
              <span>•</span>
              <span>Type: {getMeasurementTypeDescriptor(selectedStation)}</span>
              <span>•</span>
              <span
                className={
                  selectedStation.freshness_status === 'live'
                    ? 'text-emerald-400 font-semibold'
                    : selectedStation.freshness_status === 'stale'
                    ? 'text-amber-400 font-semibold'
                    : 'text-rose-400 font-semibold'
                }
              >
                Freshness: {selectedStation.freshness_status.toUpperCase()}
                {selectedStation.observed_at
                  ? ` (${new Date(selectedStation.observed_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })})`
                  : ' (Missing timestamp)'}
              </span>
            </div>
            {selectedStation.unavailable_reason && (
              <p className="text-[11px] text-gray-400 italic">{selectedStation.unavailable_reason}</p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-4 border-t lg:border-t-0 lg:border-l border-gray-800 pt-3 lg:pt-0 lg:pl-5 shrink-0">
            <div className="text-right">
              <div className="text-[10px] uppercase font-semibold text-gray-400">
                {selectedStation.measurement_type === 'provider_index'
                  ? `WAQI ${selectedPollutant.toUpperCase()} Index`
                  : `${selectedPollutant.toUpperCase()} Concentration`}
              </div>
              <div className="text-lg font-bold text-white">
                {selectedStation.measurement_type === 'provider_index' && selectedStation.provider_index !== null ? (
                  <>
                    {selectedStation.provider_index}{' '}
                    <span className="text-xs font-normal text-indigo-300">US-EPA AQI</span>
                  </>
                ) : selectedStation.concentration !== null ? (
                  <>
                    {selectedStation.concentration}{' '}
                    <span className="text-xs font-normal text-gray-400">{mapData?.unit}</span>
                  </>
                ) : (
                  <span className="text-sm font-medium text-gray-500">Not provided</span>
                )}
              </div>
            </div>

            <div className="text-right border-l border-gray-800 pl-4">
              <div className="text-[10px] uppercase font-semibold text-gray-400">CPCB Sub-Index</div>
              <div className="text-lg font-bold text-blue-400">
                {selectedStation.cpcb_sub_index !== null ? (
                  Math.round(selectedStation.cpcb_sub_index)
                ) : (
                  <span className="text-xs font-medium text-gray-500">Unavailable</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Provenance and Disclaimer Note */}
      <div className="text-[11px] text-gray-500 flex items-start gap-2">
        <Info className="w-3.5 h-3.5 text-gray-400 shrink-0 mt-0.5" />
        <p>
          {summary?.data_provenance_note || 'Displaying available environmental monitoring telemetry.'} BreatheWise AI
          distinguishes WAQI provider sub-indices, raw mass concentrations, and CAMS model estimates rather than mixing
          incompatible scales.
        </p>
      </div>
    </section>
  );
};
