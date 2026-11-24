import React from 'react';
import { NormalizedAirObservation } from '@/types/air-quality';
import { ShieldAlert, ShieldCheck, Activity, AlertTriangle } from 'lucide-react';

interface Props {
  observation: NormalizedAirObservation;
}

export const AirQualityHero: React.FC<Props> = ({ observation }) => {
  const { index_value, index_category, city, locality_or_station } = observation;

  const getCategoryStyles = () => {
    switch (index_category) {
      case 'Good':
        return {
          bg: 'from-emerald-500 to-green-600',
          badgeBg: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-200',
          border: 'border-emerald-300 dark:border-emerald-800',
          icon: <ShieldCheck className="w-8 h-8 text-emerald-400" />,
          healthText: 'Minimal health impact. Ambient air conditions are ideal for outdoor physical activities.',
        };
      case 'Satisfactory':
        return {
          bg: 'from-lime-500 to-emerald-600',
          badgeBg: 'bg-lime-100 text-lime-800 dark:bg-lime-900/60 dark:text-lime-200',
          border: 'border-lime-300 dark:border-lime-800',
          icon: <ShieldCheck className="w-8 h-8 text-lime-400" />,
          healthText: 'Minor breathing discomfort possible for sensitive individuals during prolonged intense exertion.',
        };
      case 'Moderate':
        return {
          bg: 'from-amber-500 to-yellow-600',
          badgeBg: 'bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-200',
          border: 'border-amber-300 dark:border-amber-800',
          icon: <Activity className="w-8 h-8 text-amber-400" />,
          healthText: 'May cause breathing discomfort to individuals with lung diseases (asthma) and heart conditions.',
        };
      case 'Poor':
        return {
          bg: 'from-orange-500 to-amber-700',
          badgeBg: 'bg-orange-100 text-orange-800 dark:bg-orange-900/60 dark:text-orange-200',
          border: 'border-orange-300 dark:border-orange-800',
          icon: <AlertTriangle className="w-8 h-8 text-orange-400" />,
          healthText: 'Breathing discomfort to most people on prolonged exposure. Vulnerable groups avoid strenuous exertion.',
        };
      case 'Very Poor':
        return {
          bg: 'from-rose-600 to-red-700',
          badgeBg: 'bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-200',
          border: 'border-rose-300 dark:border-rose-800',
          icon: <ShieldAlert className="w-8 h-8 text-rose-300 animate-pulse" />,
          healthText: 'Respiratory illness on prolonged exposure. Significantly affects children, seniors, and pre-existing conditions.',
        };
      case 'Severe':
        return {
          bg: 'from-purple-800 to-rose-950',
          badgeBg: 'bg-purple-100 text-purple-900 dark:bg-purple-950 dark:text-purple-200',
          border: 'border-purple-400 dark:border-purple-800',
          icon: <ShieldAlert className="w-8 h-8 text-purple-300 animate-bounce" />,
          healthText: 'Severe health hazard. Affects healthy people and seriously impacts vulnerable individuals. Minimize outdoor transit.',
        };
      default:
        return {
          bg: 'from-slate-600 to-slate-800',
          badgeBg: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200',
          border: 'border-slate-300 dark:border-slate-700',
          icon: <AlertTriangle className="w-8 h-8 text-slate-400" />,
          healthText: 'Telemetry unavailable for this location. Please check alternative nearby stations.',
        };
    }
  };

  const style = getCategoryStyles();

  return (
    <div className={`relative overflow-hidden rounded-2xl border ${style.border} bg-gradient-to-br ${style.bg} text-white p-6 sm:p-8 shadow-xl shadow-slate-900/10`}>
      <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm font-medium tracking-wide uppercase text-white/80">
              Current Air Quality • {city}
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            {locality_or_station || city}
          </h1>
          <p className="mt-2 text-sm text-white/90 max-w-xl leading-relaxed">
            {style.healthText}
          </p>
        </div>

        <div className="flex items-center gap-5 self-start md:self-auto bg-black/20 backdrop-blur-md px-6 py-4 rounded-2xl border border-white/10">
          <div className="text-right">
            <div className="text-4xl sm:text-5xl font-black tracking-tight font-mono">
              {index_value !== null ? index_value : '--'}
            </div>
            <div className="text-xs font-semibold uppercase tracking-wider text-white/80 mt-0.5">
              CPCB Index Band
            </div>
          </div>
          <div className="w-px h-12 bg-white/20" />
          <div className="flex flex-col items-center">
            {style.icon}
            <span className="text-xs font-bold mt-1 uppercase tracking-wider text-white">
              {index_category}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
