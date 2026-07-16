export type Zone = {
  key: string;
  name: string;
  kind: 'cultural' | 'restricted';
  lat: number;
  lng: number;
  radiusKm: number;
  rules: string[];
};

export const zones: Zone[] = [
  {
    key: 'tooth',
    name: 'Temple of the Sacred Tooth Relic, Kandy',
    kind: 'cultural',
    lat: 7.2936,
    lng: 80.6413,
    radiusKm: 1.2,
    rules: [
      'Cover shoulders and knees. White or light clothing is customary.',
      'Remove footwear and hats before entering the temple grounds.',
      'Never pose with your back to a Buddha image.',
      'Photography of the relic chamber is not permitted.',
    ],
  },
  {
    key: 'anuradhapura',
    name: 'Anuradhapura Sacred City',
    kind: 'cultural',
    lat: 8.3542,
    lng: 80.3964,
    radiusKm: 6,
    rules: [
      'This is a living sacred site, not only ruins. Dress modestly throughout.',
      'Remove shoes at every dagoba platform, including outdoor areas.',
      'Do not climb on or touch stupas, statues or moonstones.',
      'Sit with feet pointing away from Buddha images.',
    ],
  },
  {
    key: 'polonnaruwa',
    name: 'Polonnaruwa Ancient City',
    kind: 'cultural',
    lat: 7.9403,
    lng: 81.0188,
    radiusKm: 5,
    rules: [
      'Cover shoulders and knees across the quadrangle.',
      'Remove footwear at Gal Vihara and all temple platforms.',
      'Selfies with your back to the reclining Buddha are a criminal offence.',
      'Drones are prohibited without Department of Archaeology approval.',
    ],
  },
  {
    key: 'dalada-adams',
    name: 'Adam\u2019s Peak (Sri Pada)',
    kind: 'cultural',
    lat: 6.8096,
    lng: 80.4994,
    radiusKm: 3,
    rules: [
      'A pilgrimage site for four religions. Keep noise down on the ascent.',
      'Remove footwear at the summit platform.',
      'Do not litter on the trail.',
    ],
  },
  {
    key: 'sigiriya',
    name: 'Sigiriya Rock Fortress',
    kind: 'restricted',
    lat: 7.9571,
    lng: 80.7603,
    radiusKm: 5,
    rules: [
      'DRONE NO-FLY ZONE. Archaeological protection applies to the entire rock.',
      'Flying without CAASL and Ministry of Defence clearance is a criminal offence.',
      'Penalties reach LKR 60,000 and up to 6 months imprisonment.',
      'Photography of the frescoes is prohibited.',
    ],
  },
  {
    key: 'colombo-fort',
    name: 'Colombo Fort Government Zone',
    kind: 'restricted',
    lat: 6.9344,
    lng: 79.8428,
    radiusKm: 2.5,
    rules: [
      'DRONE NO-FLY ZONE. Government and naval installations.',
      'Do not photograph checkpoints, military vehicles or personnel.',
      'Keep cameras lowered when passing security cordons.',
    ],
  },
  {
    key: 'katunayake',
    name: 'Bandaranaike International Airport',
    kind: 'restricted',
    lat: 7.1808,
    lng: 79.8841,
    radiusKm: 8,
    rules: [
      'DRONE NO-FLY ZONE. Controlled airspace, 8 km radius.',
      'No exceptions are granted for sub-250g aircraft.',
      'Aviation offences are prosecuted under the Civil Aviation Act.',
    ],
  },
  {
    key: 'trinco-naval',
    name: 'Trincomalee Naval Dockyard',
    kind: 'restricted',
    lat: 8.5667,
    lng: 81.2167,
    radiusKm: 4,
    rules: [
      'DRONE NO-FLY ZONE. Active naval base.',
      'Photography of the harbour and vessels is prohibited.',
    ],
  },
];
