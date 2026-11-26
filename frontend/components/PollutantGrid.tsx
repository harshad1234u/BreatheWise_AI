import React from 'react';
import { NormalizedAirObservation, PollutantConcentration } from '@/types/air-quality';
import { Wind, Flame, Eye, Sparkles } from 'lucide-react';

interface Props {
  observation: NormalizedAirObservation;
}

interface PollutantMeta {
  key: keyof Pick<NormalizedAirObservation, 'pm25' | 'pm10' | 'no2' | 'so2' | 'co' | 'o3' | 'nh3' | 'pb'>;
  label: string;
  name: string;
  desc: string;
  icon: React.ReactNode;
}

const POLLUTANTS: PollutantMeta[] = [
  {
    key: 'pm25',
    label: 'PM2.5',
    name: 'Fine Particulates',
    desc: 'Combustion particles, organic compounds, metals (<2.5 µm)',
    icon: <Wind className="w-4 h-4 text-rose-500" />,
  },
  {
    key: 'pm10',
    label: 'PM10',
    name: 'Coarse Particulates',
    desc: 'Road dust, construction dust, pollen, spores (<10 µm)',
    icon: <Wind className="w-4 h-4 text-amber-500" />,
  },
  {
    key: 'no2',
    label: 'NO₂',
    name: 'Nitrogen Dioxide',
    desc: 'Vehicular exhaust & industrial fuel combustion',
    icon: <Flame className="w-4 h-4 text-orange-500" />,
  },
  {
    key: 'o3',
    label: 'O₃',
    name: 'Ground Ozone',
    desc: 'Photochemical smog formed by sunlight and traffic emissions',
    icon: <Sparkles className="w-4 h-4 text-blue-500" />,
  },
  {
    key: 'so2',
    label: 'SO₂',
    name: 'Sulfur Dioxide',
    desc: 'Thermal power plants & heavy industrial fuel burning',
    icon: <Eye className="w-4 h-4 text-yellow-500" />,
  },
  {
    key: 'co',
    label: 'CO',
    name: 'Carbon Monoxide',
    desc: 'Incomplete combustion from vehicles & biomass',
    icon: <Flame className="w-4 h-4 text-red-500" />,
  },
  {
    key: 'nh3',
    label: 'NH₃',
    name: 'Ammonia',
    desc: 'Agricultural emissions, fertilizer & livestock waste decomposition',
    icon: <Sparkles className="w-4 h-4 text-emerald-500" />,
  },
  {
    key: 'pb',
    label: 'Pb',
    name: 'Lead',
    desc: 'Industrial smelting, battery manufacturing & legacy particulates',
    icon: <Eye className="w-4 h-4 text-purple-500" />,
  },
];

export const PollutantGrid: React.FC<Props> = ({ observation }) => {
  const getSubIndexColor = (subIndex: number | null) => {
    if (subIndex === null) return 'text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800';
    if (subIndex <= 50) return 'text-emerald-800 bg-emerald-100 dark:bg-emerald-950 dark:text-emerald-300';
    if (subIndex <= 100) return 'text-lime-800 bg-lime-100 dark:bg-lime-950 dark:text-lime-300';
    if (subIndex <= 200) return 'text-amber-800 bg-amber-100 dark:bg-amber-950 dark:text-amber-300';
    if (subIndex <= 300) return 'text-orange-800 bg-orange-100 dark:bg-orange-950 dark:text-orange-300';
    if (subIndex <= 400) return 'text-rose-800 bg-rose-100 dark:bg-rose-950 dark:text-rose-300';
    return 'text-purple-800 bg-purple-100 dark:bg-purple-950 dark:text-purple-300';
  };

  const getSubIndexCategory = (subIndex: number | null): string => {
    if (subIndex === null) return 'Unavailable';
    if (subIndex <= 50) return 'Good';
    if (subIndex <= 100) return 'Satisfactory';
    if (subIndex <= 200) return 'Moderate';
    if (subIndex <= 300) return 'Poor';
    if (subIndex <= 400) return 'Very Poor';
    return 'Severe';
  };

  return (
    <section aria-labelledby="pollutants-heading" className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 id="pollutants-heading" className="text-lg font-bold text-slate-900 dark:text-white">
          Criteria Pollutants Breakdown
        </h2>
        <span className="text-xs text-slate-600 dark:text-slate-300">
          {observation.index_type === 'provider_index'
            ? 'WAQI provider sub-indices (raw concentrations unavailable)'
            : 'Evaluated via CPCB sub-index breakpoints'}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {POLLUTANTS.map((item) => {
          const pData = observation[item.key] as PollutantConcentration | null;

          return (
            <div
              key={item.key}
              className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300 dark:hover:border-slate-700 transition shadow-sm"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800">
                    {item.icon}
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                      {item.label}
                    </h3>
                    <span className="block text-[11px] text-slate-600 dark:text-slate-300 font-medium">
                      {item.name}
                    </span>
                  </div>
                </div>

                {pData && pData.sub_index !== null ? (
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-bold font-mono ${getSubIndexColor(
                      pData.sub_index
                    )}`}
                  >
                    Sub-index: {Math.round(pData.sub_index)} • {getSubIndexCategory(pData.sub_index)}
                  </span>
                ) : (
                  <span className="text-xs text-slate-600 dark:text-slate-300">--</span>
                )}
              </div>

              <div className="mt-4 flex items-baseline justify-between">
                <div>
                  <span className="text-2xl font-black font-mono tracking-tight text-slate-900 dark:text-white">
                    {pData && pData.value !== null ? pData.value.toFixed(1) : '--'}
                  </span>
                  <span className="ml-1 text-xs text-slate-600 dark:text-slate-300 font-medium">
                    {pData?.unit || 'µg/m³'}
                  </span>
                  {pData?.is_converted && (
                    <span
                      className="block text-[10px] text-slate-600 dark:text-slate-300 font-medium mt-0.5"
                      title={`Converted from ${pData.source_unit || 'ppb/ppm'} at assumed 25°C, 1 atm (24.45 L/mol)`}
                    >
                      Approx. from {pData.source_unit || 'ppb/ppm'} (25°C/1 atm)
                    </span>
                  )}
                </div>
                <span className="text-[11px] text-slate-600 dark:text-slate-300">
                  {pData?.averaging_period_hours || 1}h avg
                </span>
              </div>

              <p className="mt-2 text-[11px] text-slate-600 dark:text-slate-300 line-clamp-1">
                {item.desc}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
};
