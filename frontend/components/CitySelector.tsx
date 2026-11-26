import React from 'react';
import { CityMetadata } from '@/types/air-quality';
import { MapPin } from 'lucide-react';

interface Props {
  cities: CityMetadata[];
  selectedCityId: string;
  onSelectCity: (cityId: string) => void;
  isLoading: boolean;
}

export const CitySelector: React.FC<Props> = ({
  cities,
  selectedCityId,
  onSelectCity,
  isLoading,
}) => {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
      <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300 font-semibold text-sm">
        <MapPin className="w-4 h-4 text-teal-600 dark:text-teal-400" />
        <span>Select Indian Metropolitan Region:</span>
      </div>

      <div
        className="flex flex-wrap items-center gap-2"
        role="group"
        aria-label="Select Indian Metropolitan Region"
      >
        {cities.map((city) => {
          const isSelected = city.id === selectedCityId;
          return (
            <button
              key={city.id}
              type="button"
              onClick={() => onSelectCity(city.id)}
              disabled={isLoading}
              aria-pressed={isSelected}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150 cursor-pointer ${
                isSelected
                  ? 'bg-teal-600 text-white shadow-sm shadow-teal-600/30 ring-2 ring-teal-600 ring-offset-2 dark:ring-offset-slate-900'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
              } ${isLoading ? 'opacity-70 cursor-not-allowed' : ''}`}
            >
              {city.name}
            </button>
          );
        })}
      </div>
    </div>
  );
};
