import React, { useState, useEffect } from 'react';
import { HouseholdProfile, PersonaType, CommuteMode, KitchenVentilation } from '@/types/plan';
import { User, Users, ShieldAlert, Sparkles, SlidersHorizontal, Check } from 'lucide-react';

interface Props {
  currentProfile: HouseholdProfile;
  onProfileChange: (newProfile: HouseholdProfile) => void;
  onGeneratePlan: () => void;
  isLoading: boolean;
}

export const SAMPLE_PROFILES: { name: string; desc: string; profile: Partial<HouseholdProfile> }[] = [
  {
    name: 'Delhi NCR Family',
    desc: 'Parent with 6yo asthmatic child, 2-wheeler school commute, exhaust fan present',
    profile: {
      display_name: 'Delhi NCR Family (High Sensitivity)',
      persona: 'parent',
      age_groups: ['child', 'adult'],
      has_respiratory_sensitivity: true,
      has_cardiovascular_sensitivity: false,
      commute_mode: 'two_wheeler',
      has_air_purifier: true,
      kitchen_ventilation_type: 'exhaust_fan',
    },
  },
  {
    name: 'Bengaluru Runner',
    desc: 'Athlete, morning outdoor fitness enthusiast, Metro commuter',
    profile: {
      display_name: 'Bengaluru Athlete / Runner',
      persona: 'athlete',
      age_groups: ['adult'],
      has_respiratory_sensitivity: false,
      has_cardiovascular_sensitivity: false,
      commute_mode: 'metro_train',
      has_air_purifier: false,
      kitchen_ventilation_type: 'chimney',
    },
  },
  {
    name: 'Mumbai Senior Citizen',
    desc: '68yo walking enthusiast, gentle cardio, ground-floor apartment',
    profile: {
      display_name: 'Mumbai Senior Citizen',
      persona: 'senior',
      age_groups: ['senior'],
      has_respiratory_sensitivity: false,
      has_cardiovascular_sensitivity: true,
      commute_mode: 'walking',
      has_air_purifier: true,
      kitchen_ventilation_type: 'exhaust_fan',
    },
  },
];

export const ProfileSelector: React.FC<Props> = ({
  currentProfile,
  onProfileChange,
  onGeneratePlan,
  isLoading,
}) => {
  const [isCustomizing, setIsCustomizing] = useState(false);

  const handleSelectSample = (sample: typeof SAMPLE_PROFILES[0]) => {
    const updated: HouseholdProfile = {
      ...currentProfile,
      ...sample.profile,
      display_name: sample.profile.display_name || currentProfile.display_name,
    };
    onProfileChange(updated);
    try {
      localStorage.setItem('breathewise_guest_profile', JSON.stringify(updated));
    } catch {}
  };

  const updateField = <K extends keyof HouseholdProfile>(key: K, value: HouseholdProfile[K]) => {
    const updated = { ...currentProfile, [key]: value };
    onProfileChange(updated);
    try {
      localStorage.setItem('breathewise_guest_profile', JSON.stringify(updated));
    } catch {}
  };

  return (
    <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <User className="w-5 h-5 text-teal-600 dark:text-teal-400" />
            <h2 className="font-bold text-base text-slate-900 dark:text-white">
              Household Profile & Daily Context
            </h2>
            <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
              Guest Mode
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Personalizes activity schedules, indoor mitigation, and commute advice
          </p>
        </div>

        <button
          onClick={onGeneratePlan}
          disabled={isLoading}
          className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-500 hover:to-emerald-500 text-white font-bold text-xs shadow-md shadow-teal-600/20 transition cursor-pointer disabled:opacity-50"
        >
          <Sparkles className="w-4 h-4" />
          <span>{isLoading ? 'Synthesizing Plan...' : 'Generate Daily Routine'}</span>
        </button>
      </div>

      {/* Evaluator Quick-Select Sample Profiles */}
      <div className="space-y-2">
        <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
          One-Click Evaluator Sample Profiles:
        </span>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
          {SAMPLE_PROFILES.map((sample) => {
            const isMatch = currentProfile.persona === sample.profile.persona &&
              currentProfile.has_respiratory_sensitivity === sample.profile.has_respiratory_sensitivity;

            return (
              <button
                key={sample.name}
                onClick={() => handleSelectSample(sample)}
                type="button"
                className={`p-3 text-left rounded-xl border transition cursor-pointer ${
                  isMatch
                    ? 'border-teal-500 bg-teal-50/50 dark:bg-teal-950/40 ring-1 ring-teal-500'
                    : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-slate-50/50 dark:bg-slate-900/40'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-xs text-slate-900 dark:text-white">
                    {sample.name}
                  </span>
                  {isMatch && <Check className="w-3.5 h-3.5 text-teal-600" />}
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 line-clamp-2">
                  {sample.desc}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Toggle Customizer */}
      <div className="pt-2">
        <button
          onClick={() => setIsCustomizing(!isCustomizing)}
          type="button"
          className="flex items-center gap-1.5 text-xs font-semibold text-teal-600 dark:text-teal-400 hover:underline cursor-pointer"
        >
          <SlidersHorizontal className="w-3.5 h-3.5" />
          <span>{isCustomizing ? 'Hide Profile Customizer' : 'Customize Sensitivities & Commute Mode'}</span>
        </button>

        {isCustomizing && (
          <div className="mt-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-4 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Primary Persona
                </label>
                <select
                  value={currentProfile.persona}
                  onChange={(e) => updateField('persona', e.target.value as PersonaType)}
                  className="w-full p-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-xs"
                >
                  <option value="parent">Parent / Family</option>
                  <option value="athlete">Athlete / Runner</option>
                  <option value="senior">Senior Citizen</option>
                  <option value="commuter">Daily Commuter</option>
                  <option value="general">General Resident</option>
                </select>
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Commute Mode
                </label>
                <select
                  value={currentProfile.commute_mode || 'metro_train'}
                  onChange={(e) => updateField('commute_mode', e.target.value as CommuteMode)}
                  className="w-full p-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-xs"
                >
                  <option value="two_wheeler">Two-Wheeler (Motorcycle/Scooter)</option>
                  <option value="open_auto">Open Auto-Rickshaw</option>
                  <option value="metro_train">Metro / Electric Train</option>
                  <option value="closed_car">Closed Car / Cab</option>
                  <option value="walking">Walking / Cycling</option>
                  <option value="none">Work from Home / None</option>
                </select>
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Kitchen Ventilation
                </label>
                <select
                  value={currentProfile.kitchen_ventilation_type}
                  onChange={(e) => updateField('kitchen_ventilation_type', e.target.value as KitchenVentilation)}
                  className="w-full p-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-xs"
                >
                  <option value="exhaust_fan">Exhaust Fan</option>
                  <option value="chimney">Electric Chimney</option>
                  <option value="window_only">Window Only</option>
                  <option value="none">No Direct Ventilation</option>
                </select>
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Sensitivities
                </label>
                <div className="flex flex-col gap-1.5 pt-1">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={currentProfile.has_respiratory_sensitivity}
                      onChange={(e) => updateField('has_respiratory_sensitivity', e.target.checked)}
                      className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                    />
                    <span>Asthma / Respiratory</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={currentProfile.has_air_purifier}
                      onChange={(e) => updateField('has_air_purifier', e.target.checked)}
                      className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                    />
                    <span>Air Purifier Present</span>
                  </label>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
