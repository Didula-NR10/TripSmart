export type District = {
  key: string;
  name: string;
  province: string;
  zone: 'wet' | 'dry' | 'intermediate';
  lat: number;
  lng: number;
  bbox: [number, number, number, number];
  elevation: number;
};

export const districts: District[] = [
  { key: 'colombo', name: 'Colombo', province: 'Western', zone: 'wet', lat: 6.9271, lng: 79.8612, bbox: [6.75, 79.82, 7.05, 80.15], elevation: 5 },
  { key: 'gampaha', name: 'Gampaha', province: 'Western', zone: 'wet', lat: 7.0917, lng: 79.9998, bbox: [6.95, 79.82, 7.35, 80.25], elevation: 15 },
  { key: 'kalutara', name: 'Kalutara', province: 'Western', zone: 'wet', lat: 6.5854, lng: 79.9607, bbox: [6.35, 79.9, 6.85, 80.35], elevation: 10 },
  { key: 'kandy', name: 'Kandy', province: 'Central', zone: 'wet', lat: 7.2906, lng: 80.6337, bbox: [7.0, 80.35, 7.55, 81.0], elevation: 500 },
  { key: 'matale', name: 'Matale', province: 'Central', zone: 'intermediate', lat: 7.4675, lng: 80.6234, bbox: [7.35, 80.35, 7.95, 81.05], elevation: 364 },
  { key: 'nuwaraeliya', name: 'Nuwara Eliya', province: 'Central', zone: 'wet', lat: 6.9497, lng: 80.7891, bbox: [6.75, 80.5, 7.15, 81.05], elevation: 1868 },
  { key: 'galle', name: 'Galle', province: 'Southern', zone: 'wet', lat: 6.0535, lng: 80.221, bbox: [5.92, 80.0, 6.4, 80.45], elevation: 13 },
  { key: 'matara', name: 'Matara', province: 'Southern', zone: 'wet', lat: 5.9549, lng: 80.555, bbox: [5.9, 80.35, 6.35, 80.8], elevation: 8 },
  { key: 'hambantota', name: 'Hambantota', province: 'Southern', zone: 'dry', lat: 6.1241, lng: 81.1185, bbox: [6.0, 80.75, 6.6, 81.6], elevation: 15 },
  { key: 'jaffna', name: 'Jaffna', province: 'Northern', zone: 'dry', lat: 9.6615, lng: 80.0255, bbox: [9.5, 79.85, 9.85, 80.35], elevation: 5 },
  { key: 'kilinochchi', name: 'Kilinochchi', province: 'Northern', zone: 'dry', lat: 9.3803, lng: 80.377, bbox: [9.15, 80.05, 9.55, 80.75], elevation: 20 },
  { key: 'mannar', name: 'Mannar', province: 'Northern', zone: 'dry', lat: 8.9779, lng: 79.9042, bbox: [8.65, 79.7, 9.35, 80.35], elevation: 5 },
  { key: 'vavuniya', name: 'Vavuniya', province: 'Northern', zone: 'dry', lat: 8.7514, lng: 80.4971, bbox: [8.5, 80.2, 9.15, 80.95], elevation: 100 },
  { key: 'mullaitivu', name: 'Mullaitivu', province: 'Northern', zone: 'dry', lat: 9.2671, lng: 80.8142, bbox: [8.95, 80.5, 9.5, 81.05], elevation: 10 },
  { key: 'batticaloa', name: 'Batticaloa', province: 'Eastern', zone: 'dry', lat: 7.7102, lng: 81.6924, bbox: [7.4, 81.4, 8.2, 81.9], elevation: 5 },
  { key: 'ampara', name: 'Ampara', province: 'Eastern', zone: 'dry', lat: 7.2917, lng: 81.6725, bbox: [6.6, 81.2, 7.55, 81.95], elevation: 25 },
  { key: 'trincomalee', name: 'Trincomalee', province: 'Eastern', zone: 'dry', lat: 8.5874, lng: 81.2152, bbox: [8.2, 80.85, 9.0, 81.35], elevation: 8 },
  { key: 'kurunegala', name: 'Kurunegala', province: 'North Western', zone: 'intermediate', lat: 7.4863, lng: 80.3647, bbox: [7.2, 79.95, 8.15, 80.75], elevation: 116 },
  { key: 'puttalam', name: 'Puttalam', province: 'North Western', zone: 'dry', lat: 8.0362, lng: 79.8283, bbox: [7.35, 79.7, 8.45, 80.2], elevation: 5 },
  { key: 'anuradhapura', name: 'Anuradhapura', province: 'North Central', zone: 'dry', lat: 8.3114, lng: 80.4037, bbox: [7.9, 80.0, 9.0, 81.0], elevation: 81 },
  { key: 'polonnaruwa', name: 'Polonnaruwa', province: 'North Central', zone: 'dry', lat: 7.9403, lng: 81.0188, bbox: [7.6, 80.7, 8.4, 81.4], elevation: 60 },
  { key: 'badulla', name: 'Badulla', province: 'Uva', zone: 'intermediate', lat: 6.9895, lng: 81.0557, bbox: [6.65, 80.75, 7.4, 81.45], elevation: 680 },
  { key: 'monaragala', name: 'Monaragala', province: 'Uva', zone: 'dry', lat: 6.8728, lng: 81.351, bbox: [6.35, 80.95, 7.35, 81.85], elevation: 150 },
  { key: 'ratnapura', name: 'Ratnapura', province: 'Sabaragamuwa', zone: 'wet', lat: 6.6828, lng: 80.3992, bbox: [6.3, 80.15, 6.95, 80.85], elevation: 34 },
  { key: 'kegalle', name: 'Kegalle', province: 'Sabaragamuwa', zone: 'wet', lat: 7.2513, lng: 80.3464, bbox: [6.95, 80.1, 7.45, 80.65], elevation: 156 },
];

export const districtByKey = (key: string) => districts.find((d) => d.key === key);
