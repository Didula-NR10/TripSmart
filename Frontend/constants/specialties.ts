import data from './district-specialties.json';
import { districtByKey } from './districts';

export type SpecialtyCategory =
  | 'food'
  | 'drink'
  | 'dessert'
  | 'craft'
  | 'gem_mineral'
  | 'agri_produce'
  | 'textile';

export type Specialty = {
  category: SpecialtyCategory;
  name: string;
  description: string;
  notification_text: string;
};

type DistrictBlock = {
  district: string;
  province: string;
  items: Specialty[];
};

const blocks = (data as any).districts as DistrictBlock[];

const byName = new Map(blocks.map((b) => [b.district, b]));

export function specialtiesForDistrict(districtKey: string): Specialty[] {
  const name = districtByKey(districtKey)?.name;
  if (!name) return [];
  return byName.get(name)?.items ?? [];
}

export function allSpecialties(): (Specialty & { district: string })[] {
  return blocks.flatMap((b) => b.items.map((item) => ({ ...item, district: b.district })));
}

export function provinceForDistrict(districtKey: string): string | null {
  const name = districtByKey(districtKey)?.name;
  if (!name) return null;
  return byName.get(name)?.province ?? null;
}

export const specialtyCategoryLabel: Record<SpecialtyCategory, string> = {
  food: 'Food',
  drink: 'Drink',
  dessert: 'Dessert',
  craft: 'Craft',
  gem_mineral: 'Gems & minerals',
  agri_produce: 'Farm produce',
  textile: 'Textile',
};
