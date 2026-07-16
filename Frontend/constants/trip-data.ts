export const heroImage = {
  uri: 'https://images.unsplash.com/photo-1641149750086-b11cd21d1f60?w=1200&q=80',
};

export const conditions = {
  city: 'Colombo',
  country: 'Sri Lanka',
  district: 'Colombo District',
  temp: 29,
  feelsLike: 32,
  summary: 'Partly Cloudy',
  wind: '14 km/h',
  humidity: '78%',
  visibility: '14 km',
};

export const bestWindow = {
  start: '8:00',
  end: '11:30 AM',
  dayStart: 6,
  dayEnd: 18,
  from: 8,
  to: 11.5,
  reasons: ['Low humidity', 'Clear skies', 'UV below 6', 'Ideal for outdoor sites'],
  ticks: ['6 AM', '9 AM', '12 PM', '3 PM', '6 PM'],
};

export type HourSlot = {
  key: string;
  label: string;
  temp: number;
  icon: 'sunny' | 'partly' | 'cloud';
  active: boolean;
};

export const hourly: HourSlot[] = [
  { key: 'h6', label: '6 AM', temp: 25, icon: 'partly', active: false },
  { key: 'h7', label: '7 AM', temp: 26, icon: 'sunny', active: false },
  { key: 'h8', label: '8 AM', temp: 27, icon: 'sunny', active: true },
  { key: 'h9', label: '9 AM', temp: 28, icon: 'sunny', active: true },
  { key: 'h10', label: '10 AM', temp: 30, icon: 'sunny', active: true },
  { key: 'h11', label: '11 AM', temp: 31, icon: 'sunny', active: true },
  { key: 'h12', label: '12 PM', temp: 31, icon: 'partly', active: false },
];

export type Destination = {
  key: string;
  name: string;
  district: string;
  temp: number;
  tag: string;
  tagTone: 'primary' | 'neutral';
  image: { uri: string };
};

export const destinations: Destination[] = [
  {
    key: 'sigiriya',
    name: 'Sigiriya',
    district: 'Matale',
    temp: 31,
    tag: 'Sunny',
    tagTone: 'primary',
    image: { uri: 'https://images.unsplash.com/photo-1586094340254-2b1e5e6f0d3a?w=800&q=80' },
  },
  {
    key: 'ella',
    name: 'Ella',
    district: 'Badulla',
    temp: 22,
    tag: 'Misty',
    tagTone: 'neutral',
    image: { uri: 'https://images.unsplash.com/photo-1566296314736-6eaac1ca0cb9?w=800&q=80' },
  },
  {
    key: 'mirissa',
    name: 'Mirissa',
    district: 'Matara',
    temp: 30,
    tag: 'Clear',
    tagTone: 'primary',
    image: { uri: 'https://images.unsplash.com/photo-1552465011-b4e21bf6e79a?w=800&q=80' },
  },
  {
    key: 'nuwaraeliya',
    name: 'Nuwara Eliya',
    district: 'Central',
    temp: 19,
    tag: 'Cool',
    tagTone: 'neutral',
    image: { uri: 'https://images.unsplash.com/photo-1580889240912-c39ef3e0b0f3?w=800&q=80' },
  },
];

export function todayLine() {
  const now = new Date();
  const day = now.toLocaleDateString('en-US', { weekday: 'long' });
  const month = now.toLocaleDateString('en-US', { month: 'long' });
  return `${day} · ${month} ${now.getDate()} · ${conditions.district}`;
}
