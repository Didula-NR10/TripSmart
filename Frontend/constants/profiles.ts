export type ProfileKey = 'sightseer' | 'hiker' | 'beach';

export type Profile = {
  key: ProfileKey;
  name: string;
  blurb: string;
  icon: string;
  idealTemp: [number, number];
  maxRain: number;
  maxHumidity: number;
  maxWind: number;
};

export const profiles: Profile[] = [
  {
    key: 'sightseer',
    name: 'Sightseer',
    blurb: 'Cities, temples and ruins. Prefers dry and mild.',
    icon: 'camera-outline',
    idealTemp: [22, 30],
    maxRain: 1,
    maxHumidity: 80,
    maxWind: 30,
  },
  {
    key: 'hiker',
    name: 'Hiker',
    blurb: 'Trails and highlands. Tolerates drizzle, hates heat.',
    icon: 'trail-sign-outline',
    idealTemp: [15, 26],
    maxRain: 4,
    maxHumidity: 90,
    maxWind: 40,
  },
  {
    key: 'beach',
    name: 'Beach Lover',
    blurb: 'Sun and surf. Wants heat, cannot abide rain.',
    icon: 'sunny-outline',
    idealTemp: [27, 34],
    maxRain: 0.5,
    maxHumidity: 85,
    maxWind: 25,
  },
];

export const profileByKey = (key: ProfileKey) =>
  profiles.find((p) => p.key === key) ?? profiles[0];
