import React, { useMemo, useState } from 'react';
import { CityCatalogMetadata, CityMetadata } from '@/types/air-quality';
import { MapPin, Search, Globe2 } from 'lucide-react';

interface Props {
  cities: CityMetadata[];
  catalogMeta?: CityCatalogMetadata | null;
  selectedCityId: string;
  onSelectCity: (cityId: string) => void;
  isLoading: boolean;
}

const FEATURED_METRO_IDS = ['delhi', 'mumbai', 'bengaluru', 'hyderabad', 'kolkata', 'chennai'];

function getAvailabilityBadge(status?: string): { text: string; cls: string } {
  switch (status) {
    case 'both_available':
      return { text: 'Ground + Model', cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' };
    case 'ground_monitoring_available':
      return { text: 'Ground Station', cls: 'bg-teal-500/15 text-teal-400 border-teal-500/30' };
    case 'no_current_data':
      return { text: 'No Current Data', cls: 'bg-rose-500/15 text-rose-400 border-rose-500/30' };
    default:
      return { text: 'Model / Auto-Discover', cls: 'bg-sky-500/15 text-sky-400 border-sky-500/30' };
  }
}

export const CitySelector: React.FC<Props> = ({
  cities,
  catalogMeta,
  selectedCityId,
  onSelectCity,
  isLoading,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedState, setSelectedState] = useState('all');
  const [showExplorer, setShowExplorer] = useState(false);

  const featuredCities = useMemo(() => {
    const map = new Map(cities.map((c) => [c.id, c]));
    const list = FEATURED_METRO_IDS.map((id) => map.get(id)).filter((c): c is CityMetadata => Boolean(c));
    // Ensure currently selected non-metro city is also visible as an active pill
    const current = map.get(selectedCityId);
    if (current && !FEATURED_METRO_IDS.includes(current.id)) {
      list.unshift(current);
    }
    return list.length > 0 ? list : cities.slice(0, 6);
  }, [cities, selectedCityId]);

  const stateOptions = useMemo(() => {
    const set = new Set(cities.map((c) => c.state));
    return Array.from(set).sort();
  }, [cities]);

  const filteredCities = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return cities.filter((c) => {
      if (selectedState !== 'all' && c.state !== selectedState) return false;
      if (!q) return true;
      return (
        c.name.toLowerCase().includes(q) ||
        c.state.toLowerCase().includes(q) ||
        (c.district && c.district.toLowerCase().includes(q)) ||
        (c.aliases && c.aliases.some((a) => a.toLowerCase().includes(q)))
      );
    });
  }, [cities, searchQuery, selectedState]);

  return (
    <section
      aria-label="Indian city selection"
      className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-3"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300 font-semibold text-sm">
          <MapPin className="w-4 h-4 text-teal-600 dark:text-teal-400 shrink-0" />
          <span>Select Indian City:</span>
        </div>

        <div
          className="flex flex-wrap items-center gap-2"
          role="group"
          aria-label="Select Indian Metropolitan Region"
        >
          {featuredCities.map((city) => {
            const isSelected = city.id === selectedCityId;
            return (
              <button
                key={city.id}
                type="button"
                onClick={() => onSelectCity(city.id)}
                disabled={isSelected && isLoading}
                aria-pressed={isSelected}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150 cursor-pointer ${
                  isSelected
                    ? 'bg-teal-700 text-white shadow-sm shadow-teal-700/30 ring-2 ring-teal-700 ring-offset-2 dark:ring-offset-slate-900'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                } ${isSelected && isLoading ? 'opacity-70 cursor-not-allowed' : ''}`}
              >
                {city.name}
              </button>
            );
          })}

          <button
            type="button"
            aria-expanded={showExplorer}
            onClick={() => setShowExplorer((v) => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-teal-500/40 bg-teal-500/10 text-teal-600 dark:text-teal-400 hover:bg-teal-500/20 transition cursor-pointer"
          >
            <Globe2 className="w-3.5 h-3.5" />
            <span>
              {showExplorer
                ? 'Hide All India Explorer'
                : `All India (${catalogMeta?.states_count || 28} States • ${catalogMeta?.union_territories_count || 8} UTs)`}
            </span>
          </button>
        </div>
      </div>

      {showExplorer && (
        <div className="pt-3 border-t border-slate-200 dark:border-slate-800 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label htmlFor="pan-india-city-search" className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400 mb-1">
                Search City, District, State, or Alias
              </label>
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="pan-india-city-search"
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="e.g. Jaipur, Madurai, Guwahati, Trivandrum, Leh..."
                  className="w-full pl-8 pr-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 text-xs text-slate-900 dark:text-slate-100"
                />
              </div>
            </div>

            <div>
              <label htmlFor="pan-india-state-filter" className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400 mb-1">
                Filter by State / Union Territory ({stateOptions.length} regions)
              </label>
              <select
                id="pan-india-state-filter"
                value={selectedState}
                onChange={(e) => setSelectedState(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 text-xs text-slate-900 dark:text-slate-100"
              >
                <option value="all">All 28 States &amp; 8 Union Territories ({cities.length} cities)</option>
                {stateOptions.map((st) => (
                  <option key={st} value={st}>
                    {st}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="max-h-52 overflow-y-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 pr-1">
            {filteredCities.length === 0 ? (
              <p className="text-xs text-slate-500 col-span-full py-2">
                No matching Indian cities in catalog for &ldquo;{searchQuery}&rdquo;.
              </p>
            ) : (
              filteredCities.map((city) => {
                const isSelected = city.id === selectedCityId;
                const badge = getAvailabilityBadge(city.availability_status);
                return (
                  <button
                    key={city.id}
                    type="button"
                    disabled={isSelected && isLoading}
                    aria-pressed={isSelected}
                    onClick={() => {
                      onSelectCity(city.id);
                      setShowExplorer(false);
                    }}
                    className={`p-2.5 rounded-lg border text-left transition flex items-center justify-between gap-2 cursor-pointer ${
                      isSelected
                        ? 'border-teal-500 bg-teal-500/15'
                        : 'border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-950/60 hover:border-teal-500/40'
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="text-xs font-bold text-slate-900 dark:text-slate-100 truncate">
                        {city.name}
                      </div>
                      <div className="text-[10px] text-slate-500 dark:text-slate-400 truncate">
                        {city.state} {city.region_type === 'union_territory' ? '(UT)' : ''}
                      </div>
                    </div>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border shrink-0 ${badge.cls}`}>
                      {badge.text}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </section>
  );
};
