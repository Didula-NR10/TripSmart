/**
 * constants/laws.ts — typed access to the tourist law & ethics dataset.
 *
 * The dataset lives in tourist-laws.json (241 classified entries). Entries are
 * tagged by district display name or "ALL"; this module resolves them against
 * the app's district keys and orders them by severity so the Culture tab and
 * notifications always lead with what can actually get a visitor arrested.
 */
import data from './tourist-laws.json';
import { districtByKey } from './districts';

export type RiskLevel = 'high' | 'medium' | 'low';
export type LawType = 'law' | 'custom' | 'safety' | 'ethics';

export type LawEntry = {
  id: string;
  category: string;
  title: string;
  districts: string[];
  risk_level: RiskLevel;
  type: LawType;
  explanation: string | null;
  penalty: string | null;
  suggested_geofence_radius_m: number | null;
  sources: string[];
};

export const lawsDisclaimer: string = (data as any).meta.disclaimer;

const entries = (data as any).entries as LawEntry[];

const riskRank: Record<RiskLevel, number> = { high: 0, medium: 1, low: 2 };
const typeRank: Record<LawType, number> = { law: 0, safety: 1, custom: 2, ethics: 3 };

/** Every entry that applies in a district: district-specific first, then nationwide. */
export function lawsForDistrict(districtKey: string): LawEntry[] {
  const name = districtByKey(districtKey)?.name;
  if (!name) return [];

  return entries
    .filter((e) => e.districts.includes(name) || e.districts.includes('ALL'))
    .sort((a, b) => {
      const local = Number(b.districts.includes(name)) - Number(a.districts.includes(name));
      if (local !== 0) return local;
      if (riskRank[a.risk_level] !== riskRank[b.risk_level]) {
        return riskRank[a.risk_level] - riskRank[b.risk_level];
      }
      return typeRank[a.type] - typeRank[b.type];
    });
}

/** The single most severe district-specific rule — used for notifications. */
export function topLawForDistrict(districtKey: string): LawEntry | null {
  return lawsForDistrict(districtKey)[0] ?? null;
}

/** Every entry in the dataset, most severe first — the "All Sri Lanka" view. */
export function allLaws(): LawEntry[] {
  return [...entries].sort((a, b) => {
    if (riskRank[a.risk_level] !== riskRank[b.risk_level]) {
      return riskRank[a.risk_level] - riskRank[b.risk_level];
    }
    return typeRank[a.type] - typeRank[b.type];
  });
}

export const typeLabel: Record<LawType, string> = {
  law: 'Law',
  safety: 'Safety',
  custom: 'Etiquette',
  ethics: 'Ethics',
};
