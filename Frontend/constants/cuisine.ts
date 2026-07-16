export type Dish = {
  name: string;
  local: string;
  note: string;
};

export const cuisine: Record<string, Dish[]> = {
  colombo: [
    { name: 'Kottu Roti', local: 'කොත්තු', note: 'Chopped godamba roti stir-fried with vegetables and egg. Listen for the cleaver rhythm on the griddle.' },
    { name: 'Lamprais', local: 'ලම්ප්‍රයිස්', note: 'Dutch Burgher rice parcel baked in banana leaf with frikkadels and blachan.' },
  ],
  kandy: [
    { name: 'Kiri Bath', local: 'කිරි බත්', note: 'Milk rice cut into diamonds, eaten with lunu miris. Traditionally a morning dish.' },
    { name: 'Kandyan Curry', local: '', note: 'Milder than coastal curries, heavy on cinnamon and coconut milk.' },
  ],
  matara: [
    { name: 'Ambul Thiyal', local: 'ඇඹුල් තියල්', note: 'Sour fish curry cured with goraka. Dry, black and intensely tangy.' },
  ],
  galle: [
    { name: 'Ambul Thiyal', local: 'ඇඹුල් තියල්', note: 'The southern coast version, made with tuna and dried goraka.' },
    { name: 'Hoppers', local: 'ආප්ප', note: 'Bowl-shaped fermented rice pancake. Order egg hoppers at breakfast.' },
  ],
  hambantota: [
    { name: 'Curd & Treacle', local: 'මී කිරි', note: 'Buffalo curd in a clay pot with kithul palm treacle. The regional signature.' },
  ],
  jaffna: [
    { name: 'Jaffna Crab Curry', local: '', note: 'Fierce Tamil-style curry with roasted spice and heavy black pepper.' },
    { name: 'Odiyal Kool', local: '', note: 'Seafood broth thickened with palmyrah root flour.' },
  ],
  nuwaraeliya: [
    { name: 'Ceylon Tea', local: '', note: 'High-grown BOP from estates above 1,200 m. Bright, brisk, take it without milk.' },
    { name: 'Strawberry & Cream', local: '', note: 'A hill-country colonial leftover. Every roadside stall sells it.' },
  ],
  anuradhapura: [
    { name: 'Rice & Curry', local: 'බත් කරි', note: 'Freshwater fish and dry-zone vegetables. Ask for the beetroot curry.' },
  ],
  batticaloa: [
    { name: 'Seafood Kool', local: '', note: 'Eastern coast broth, crab and prawn heavy.' },
  ],
  trincomalee: [
    { name: 'Grilled Seer Fish', local: '', note: 'Straight off the boats at Dutch Bay. Simply charred with lime.' },
  ],
  badulla: [
    { name: 'Roti & Lunu Miris', local: '', note: 'Coconut roti with a chilli-onion sambol. Hiker fuel across Ella.' },
  ],
  negombo: [
    { name: 'Seafood Curry', local: '', note: 'Lagoon crab and prawn, Catholic-coast style.' },
  ],
};

export const dishesFor = (districtKey: string): Dish[] =>
  cuisine[districtKey] ?? [
    { name: 'Rice & Curry', local: 'බත් කරි', note: 'The national plate. Expect five or six vegetable curries around a mound of red rice.' },
    { name: 'Pol Sambol', local: 'පොල් සම්බෝල', note: 'Scraped coconut, chilli, lime and maldive fish. On every table.' },
  ];
