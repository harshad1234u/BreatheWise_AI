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

// Dynamically import Leaflet only on the client
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

function getCategoryColor(category: string): string {
  switch (category) {
    case 'Good':
      return '#10B981'; // emerald-500
    case 'Satisfactory':
      return '#84CC16'; // lime-500
    case 'Moderate':
      return '#F59E0B'; // amber-500
    case 'Poor':
      return '#F97316'; // orange-500
    case 'Very Poor':
      return '#EF4444'; // red-500
    case 'Severe':
      return '#991B1B'; // red-800
    default:
      return '#6B7280'; // gray-500
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

export const PollutantMap: React.FC<PollutantMapProps> = ({ cityId, cityName }) => {
  const [selectedPollutant, setSelectedPollutant] = useState<string>('pm25');
  const [mapData, setMapData] = useState<PollutantMapResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStation, setSelectedStation] = useState<StationMapPoint | null>(null);

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<LeafletTypes.Map | null>(null);
  const markersLayerRef = useRef<LeafletTypes.FeatureGroup | null>(null);

  // Load map data whenever city or pollutant changes
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

  // Initialize or update Leaflet Map
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

      // Initialize map if not yet created
      if (!mapInstanceRef.current) {
        const map = L.map(mapContainerRef.current, {
          center: [mapData?.city_center_lat || 28.6139, mapData?.city_center_lng || 77.2090],
          zoom: 11,
          zoomControl: true,
          scrollWheelZoom: false,
        });

        // Standard OpenStreetMap tiles (100% free, no API key required)
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

      // Clear old markers
      markersGroup.clearLayers();

      // Pan map to new city center
      map.setView([mapData.city_center_lat, mapData.city_center_lng], 11);

      if (mapData.stations.length === 0) {
        return;
      }

      mapData.stations.forEach((station) => {
        const color = getCategoryColor(station.sub_index_category);
        const isReporting = station.concentration !== null;

        const marker = L.circleMarker([station.latitude, station.longitude], {
          radius: isReporting ? 9 : 6,
          fillColor: color,
          color: '#FFFFFF',
          weight: 1.5,
          opacity: 0.9,
          fillOpacity: 0.85,
        });

        const popupContent = `
        <div style="font-family: inherit; font-size: 13px; color: #F3F4F6; background: #111827; padding: 4px; border-radius: 4px;">
          <div style="font-weight: 700; margin-bottom: 4px; color: #60A5FA;">${station.station_name}</div>
          <div style="margin-bottom: 2px;"><strong>Concentration:</strong> ${
            isReporting ? `${station.concentration} ${mapData.unit}` : '<span style="color: #9CA3AF;">Unavailable</span>'
          }</div>
          <div style="margin-bottom: 2px;"><strong>CPCB Category:</strong> <span style="color: ${color}; font-weight: 600;">${
          station.sub_index_category
        }</span></div>
          <div style="margin-bottom: 2px;"><strong>Provider:</strong> ${station.data_provider}</div>
          <div style="font-size: 11px; color: #9CA3AF;"><strong>Observed:</strong> ${new Date(
            station.observed_at
          ).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
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
          // Fallback to center
          map.setView([mapData.city_center_lat, mapData.city_center_lng], 11);
        }
      }
    }

    void renderMap();

    return () => {
      isCancelled = true;
    };
  }, [mapData]);

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
            Real monitoring station coordinates mapped across {cityName}. Values reflect actual CPCB ground sensors.
          </p>
        </div>

        {/* Refresh & Provenance Status */}
        <div className="flex items-center gap-3">
          <div className="text-right hidden sm:block">
            <div className="text-xs text-gray-400">Map Attribution</div>
            <div className="text-xs font-semibold text-gray-200">CPCB Network • WAQI Feed</div>
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

      {/* Summary KPI Strip */}
      {mapData && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-gray-950/60 p-4 rounded-xl border border-gray-800/80">
          <div>
            <div className="text-[11px] text-gray-400 uppercase font-medium">Monitoring Stations</div>
            <div className="text-base font-bold text-white mt-0.5">
              {mapData.summary.reporting_stations} <span className="text-xs font-normal text-gray-400">/ {mapData.summary.total_stations} Active</span>
            </div>
          </div>
          <div>
            <div className="text-[11px] text-gray-400 uppercase font-medium">Regional Average</div>
            <div className="text-base font-bold text-white mt-0.5">
              {mapData.summary.avg_concentration !== null
                ? `${mapData.summary.avg_concentration} ${mapData.unit}`
                : '--'}
            </div>
          </div>
          <div>
            <div className="text-[11px] text-gray-400 uppercase font-medium">Observed Range</div>
            <div className="text-base font-bold text-white mt-0.5">
              {mapData.summary.min_concentration !== null && mapData.summary.max_concentration !== null
                ? `${mapData.summary.min_concentration} - ${mapData.summary.max_concentration} ${mapData.unit}`
                : '--'}
            </div>
          </div>
          <div>
            <div className="text-[11px] text-gray-400 uppercase font-medium">Telemetry Source</div>
            <div className="text-xs font-semibold text-emerald-400 mt-1 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              Verified Sensor Grid
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

        {/* Loading Overlay */}
        {loading && (
          <div className="absolute inset-0 bg-gray-950/80 backdrop-blur-sm z-10 flex flex-col items-center justify-center gap-3" aria-live="polite" aria-busy="true">
            <RefreshCw className="w-7 h-7 text-blue-400 animate-spin" />
            <p className="text-xs text-gray-300 font-medium tracking-wide">
              Loading real monitoring station telemetry for {cityName}...
            </p>
          </div>
        )}

        {/* Network / API Error Overlay */}
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

        {/* Empty State Overlay */}
        {!loading && !error && mapData && mapData.stations.length === 0 && (
          <div className="absolute inset-0 bg-gray-950/90 z-10 flex flex-col items-center justify-center p-6 text-center">
            <AlertTriangle className="w-8 h-8 text-amber-400 mb-2" />
            <h4 className="text-sm font-bold text-gray-200">No Ground Monitoring Stations Available</h4>
            <p className="text-xs text-gray-400 mt-1 max-w-md">
              Neither ground telemetry nor grid models currently report {selectedPollutant.toUpperCase()} for {cityName}.
              Values are strictly preserved as unavailable rather than simulated.
            </p>
          </div>
        )}

        {/* In-Map CPCB Color Legend */}
        <div className="absolute bottom-3 right-3 z-10 bg-gray-900/90 backdrop-blur-md p-2.5 rounded-lg border border-gray-800 text-[11px] shadow-lg max-w-[220px]">
          <div className="font-semibold text-gray-300 mb-1.5 flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-blue-400" />
            CPCB Sub-Index Scale
          </div>
          <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[10px]">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0" />
              <span className="text-gray-300">Good (0-50)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-lime-500 shrink-0" />
              <span className="text-gray-300">Satisfactory (51-100)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 shrink-0" />
              <span className="text-gray-300">Moderate (101-200)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-orange-500 shrink-0" />
              <span className="text-gray-300">Poor (201-300)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0" />
              <span className="text-gray-300">Very Poor (301-400)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-red-800 shrink-0" />
              <span className="text-gray-300">Severe (401-500+)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Keyboard-Accessible Station Picker */}
      {mapData && mapData.stations.length > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-gray-950/60 px-4 py-3 rounded-xl border border-gray-800/80">
          <label htmlFor="station-inspector-select" className="text-xs font-semibold text-gray-300">
            Inspect Monitoring Station ({mapData.stations.length} stations):
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
                {s.station_name} — {s.concentration !== null ? `${s.concentration} ${mapData.unit}` : 'Unavailable'}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Selected Station Detailed Inspector Card */}
      {selectedStation && (
        <div className="bg-gray-950 p-4 rounded-xl border border-gray-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <MapPin className="w-4 h-4 text-blue-400 shrink-0" />
              <h4 className="text-sm font-bold text-white">{selectedStation.station_name}</h4>
              <span
                className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${getCategoryBadgeClass(
                  selectedStation.sub_index_category
                )}`}
              >
                {selectedStation.sub_index_category}
              </span>
            </div>
            <div className="text-xs text-gray-400 flex flex-wrap items-center gap-3">
              <span>
                Coordinates: {selectedStation.latitude.toFixed(4)}, {selectedStation.longitude.toFixed(4)}
              </span>
              <span>•</span>
              <span>Provider: {selectedStation.data_provider}</span>
              <span>•</span>
              <span className={selectedStation.freshness_status === 'live' ? 'text-emerald-400' : 'text-amber-400'}>
                {selectedStation.freshness_status === 'live' ? 'Fresh telemetry' : 'Stale telemetry'}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4 border-t md:border-t-0 md:border-l border-gray-800 pt-3 md:pt-0 md:pl-5">
            <div className="text-right">
              <div className="text-[10px] uppercase font-semibold text-gray-400">
                {selectedPollutant.toUpperCase()} Reading
              </div>
              <div className="text-lg font-bold text-white">
                {selectedStation.concentration !== null ? (
                  <>
                    {selectedStation.concentration}{' '}
                    <span className="text-xs font-normal text-gray-400">{mapData?.unit}</span>
                  </>
                ) : (
                  <span className="text-sm font-medium text-gray-500">Not Monitored</span>
                )}
              </div>
            </div>

            {selectedStation.cpcb_sub_index !== null && (
              <div className="text-right border-l border-gray-800 pl-4">
                <div className="text-[10px] uppercase font-semibold text-gray-400">Sub-Index</div>
                <div className="text-lg font-bold text-blue-400">
                  {Math.round(selectedStation.cpcb_sub_index)}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Provenance and Disclaimer Note */}
      <div className="text-[11px] text-gray-500 flex items-start gap-2">
        <Info className="w-3.5 h-3.5 text-gray-400 shrink-0 mt-0.5" />
        <p>
          {mapData?.summary.data_provenance_note || 'Displaying monitoring network telemetry.'} BreatheWise AI displays actual ground-station observations from the CPCB network wherever available and marks unmonitored parameters as unavailable. This visualization is intended for public health risk reduction and does not substitute official CPCB regulatory reports.
        </p>
      </div>
    </section>
  );
};
