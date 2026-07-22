/**
 * constants/district-hero.ts — one recognizable landmark photo per district.
 *
 * Powers the Forecast tab hero: picking a district (map, dropdown, or GPS)
 * swaps the background photo to that district's own famous location, not a
 * generic stock photo. Images are freely-licensed Wikimedia Commons photos
 * (stable, direct-linkable, no API key) keyed by the same district `key`
 * used everywhere else in the app (constants/districts.ts).
 */
export type DistrictHero = {
  url: string;
  landmark: string;
};

export const districtHero: Record<string, DistrictHero> = {
  colombo: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/6/62/Colombo_city_skyline_at_night.png',
    landmark: 'Colombo skyline',
  },
  gampaha: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/5/57/Negombo_Lagoon_natural_harbour.jpg',
    landmark: 'Negombo Lagoon',
  },
  kalutara: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/Kalautara_Bodhiya_1.jpg/1280px-Kalautara_Bodhiya_1.jpg',
    landmark: 'Kalutara Bodhiya',
  },
  kandy: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/e/eb/SL_Kandy_asv2020-01_img33_Sacred_Tooth_Temple.jpg/1280px-SL_Kandy_asv2020-01_img33_Sacred_Tooth_Temple.jpg',
    landmark: 'Temple of the Sacred Tooth Relic',
  },
  matale: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/e/e6/Sigiriya_%28141688197%29.jpeg',
    landmark: 'Sigiriya Rock Fortress',
  },
  nuwaraeliya: {
    url: 'https://images.unsplash.com/photo-1641149750086-b11cd21d1f60?w=1200&q=80',
    landmark: 'Nuwara Eliya tea country',
  },
  galle: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/Galle_Fort.jpg/1280px-Galle_Fort.jpg',
    landmark: 'Galle Fort',
  },
  matara: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/2/2c/Dutch_Star_Fort%2C_Matara_0691.jpg',
    landmark: 'Star Fort, Matara',
  },
  hambantota: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/e/e6/Wildlife_Preserve_Near_Kirinda%2C_Sri_Lanka.jpg',
    landmark: 'Bundala wildlife country',
  },
  jaffna: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/6/61/Nallur_Kandasamy_front_entrance.jpg',
    landmark: 'Nallur Kandaswamy Temple',
  },
  kilinochchi: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/Kilinochchi_Railway_Station_-_Sri_Lanka.jpg/1280px-Kilinochchi_Railway_Station_-_Sri_Lanka.jpg',
    landmark: 'Kilinochchi',
  },
  mannar: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/a/af/Lighthouse%2C_Talaimannar.jpg',
    landmark: 'Talaimannar Lighthouse',
  },
  vavuniya: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/9/9c/Vavuniya_City.jpg',
    landmark: 'Vavuniya',
  },
  mullaitivu: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/8/84/Mullaitivu_district_secretariat_building.jpg',
    landmark: 'Mullaitivu',
  },
  batticaloa: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/4/41/Sea_Fishing%2C_Batticaloa.jpg',
    landmark: 'Batticaloa lagoon',
  },
  ampara: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/Beach_of_Arugam_Bay.jpg/1280px-Beach_of_Arugam_Bay.jpg',
    landmark: 'Arugam Bay',
  },
  trincomalee: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/Spiritual_16.jpg/1280px-Spiritual_16.jpg',
    landmark: 'Koneswaram Temple',
  },
  kurunegala: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/65/SL_Kurunegala_asv2020-01_img05.jpg/1280px-SL_Kurunegala_asv2020-01_img05.jpg',
    landmark: 'Athugala rock, Kurunegala',
  },
  puttalam: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/19/SL_Kalpitiya_asv2020-01_img4_Fishery_harbour.jpg/1280px-SL_Kalpitiya_asv2020-01_img4_Fishery_harbour.jpg',
    landmark: 'Kalpitiya',
  },
  anuradhapura: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/SL_Anuradhapura_asv2020-01_img11_Ruwanwelisaya_Stupa.jpg/1280px-SL_Anuradhapura_asv2020-01_img11_Ruwanwelisaya_Stupa.jpg',
    landmark: 'Ruwanwelisaya',
  },
  polonnaruwa: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/e/ef/Vatadage.jpg',
    landmark: 'Vatadage, Polonnaruwa',
  },
  badulla: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/f/f8/Dunhinda.jpg',
    landmark: 'Dunhinda Falls',
  },
  monaragala: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/6/6e/Standing_Buddha_Statue_Maligawila.jpg',
    landmark: 'Maligawila Buddha Statue',
  },
  ratnapura: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/Maha_Saman_Devalaya.jpg/1280px-Maha_Saman_Devalaya.jpg',
    landmark: 'Maha Saman Devalaya',
  },
  kegalle: {
    url: 'https://upload.wikimedia.org/wikipedia/commons/5/50/Pinnawala_01.jpg',
    landmark: 'Pinnawala Elephant Orphanage',
  },
};

const fallback: DistrictHero = districtHero.colombo;

export function heroForDistrict(districtKey: string): DistrictHero {
  return districtHero[districtKey] ?? fallback;
}
