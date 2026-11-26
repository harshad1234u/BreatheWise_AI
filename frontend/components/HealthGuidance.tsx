import React from 'react';
import { IndexCategory } from '@/types/air-quality';
import { HeartPulse, Home, Car, AlertCircle } from 'lucide-react';

interface Props {
  category: IndexCategory;
}

export const HealthGuidance: React.FC<Props> = ({ category }) => {
  const getGuidanceData = () => {
    switch (category) {
      case 'Good':
      case 'Satisfactory':
        return {
          general: 'Outdoor exercise and active transit (walking, cycling) are encouraged.',
          vulnerable: 'No major restrictions. Sensitive individuals monitor for minor symptoms during intense workouts.',
          transit: 'No specialized mask required. Normal travel routines suitable.',
          indoor: 'Ideal window for whole-house natural cross-ventilation. Keep windows open during pleasant weather.',
        };
      case 'Moderate':
        return {
          general: 'Outdoor activities suitable; schedule periodic hydration and rest breaks during prolonged exertion.',
          vulnerable: 'People with asthma or cardiovascular conditions should limit prolonged intense outdoor running.',
          transit: 'Active transit suitable. Consider surgical or dust masks along heavy construction or traffic corridors.',
          indoor: 'Open windows during midday hours; close during peak morning and evening rush-hour traffic spikes.',
        };
      case 'Poor':
        return {
          general: 'Avoid high-intensity morning outdoor workouts. Substitute with indoor cardiovascular exercises.',
          vulnerable: 'Children and seniors avoid prolonged outdoor physical exertion. Suspend outdoor school sports.',
          transit: 'For open two-wheeler or auto commutes >20 mins, a well-fitted particulate respirator (N95/FFP2) is advised.',
          indoor: 'Ventilate briefly only during the midday dispersion window. Practice wet mopping (pocha) instead of dry sweeping.',
        };
      case 'Very Poor':
        return {
          general: 'Avoid outdoor running and strenuous exertion. Keep outdoor exposure strictly to essential tasks.',
          vulnerable: 'Remain indoors where feasible. Keep prescribed inhalers and medications immediately accessible.',
          transit: 'N95/FFP2 respirators strongly advised for all outdoor transit. Prefer closed public transit (Metro/cab).',
          indoor: 'Keep windows closed. Run indoor HEPA air filtration if available. Ensure kitchen exhaust is on during high-heat frying.',
        };
      case 'Severe':
        return {
          general: 'Strictly avoid non-essential outdoor travel and exertion. Work from home where feasible.',
          vulnerable: 'Strict indoor sheltering advised. Vulnerable individuals monitor peak expiratory flow and oxygen saturation.',
          transit: 'Avoid all outdoor exposure unless unavoidable. N95/FFP2 respirator essential for outdoor transit.',
          indoor: 'Keep all windows and exterior doors sealed. Wet-mop floors daily to capture settled coarse dust.',
        };
      default:
        return {
          general: 'Awaiting local telemetry data.',
          vulnerable: 'Follow general precautionary habits.',
          transit: 'Normal precautions.',
          indoor: 'Normal ventilation.',
        };
    }
  };

  const data = getGuidanceData();

  return (
    <section
      aria-labelledby="health-guidance-heading"
      className="p-6 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-4"
    >
      <div className="flex items-center gap-2 pb-3 border-b border-slate-200 dark:border-slate-800">
        <HeartPulse className="w-5 h-5 text-teal-600 dark:text-teal-400" />
        <h2 id="health-guidance-heading" className="font-bold text-base text-slate-900 dark:text-white">
          Contextual Public-Health Guidance (CPCB &amp; MoHFW Framework)
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-800">
          <h3 className="flex items-center gap-2 font-bold text-slate-800 dark:text-slate-200 mb-1">
            <span className="w-2 h-2 rounded-full bg-teal-500" aria-hidden="true" />
            <span>General Population</span>
          </h3>
          <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
            {data.general}
          </p>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-800">
          <h3 className="flex items-center gap-2 font-bold text-slate-800 dark:text-slate-200 mb-1">
            <span className="w-2 h-2 rounded-full bg-rose-500" aria-hidden="true" />
            <span>Vulnerable Cohorts (Children, Seniors, Asthma)</span>
          </h3>
          <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
            {data.vulnerable}
          </p>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-800">
          <h3 className="flex items-center gap-2 font-bold text-slate-800 dark:text-slate-200 mb-1">
            <Car className="w-4 h-4 text-indigo-500" aria-hidden="true" />
            <span>Commute &amp; Respirator Advisory</span>
          </h3>
          <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
            {data.transit}
          </p>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-800">
          <h3 className="flex items-center gap-2 font-bold text-slate-800 dark:text-slate-200 mb-1">
            <Home className="w-4 h-4 text-emerald-500" aria-hidden="true" />
            <span>Indoor Air &amp; Ventilation Intelligence</span>
          </h3>
          <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
            {data.indoor}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 text-[11px] text-slate-500 dark:text-slate-400 pt-2 border-t border-slate-100 dark:border-slate-800">
        <AlertCircle className="w-3.5 h-3.5 text-slate-400 shrink-0" aria-hidden="true" />
        <span>Advisory guidance based on MoHFW NPCCHH guidelines and CPCB health statements. Not a medical device.</span>
      </div>
    </section>
  );
};
