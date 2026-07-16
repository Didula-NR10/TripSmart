import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { dishesFor } from '../../constants/cuisine';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

export function CuisineCard({ districtKey }: { districtKey: string }) {
  const dishes = dishesFor(districtKey);

  return (
    <View style={styles.card}>
      {dishes.map((dish, i) => (
        <View key={dish.name} style={[styles.dish, i > 0 && styles.divider]}>
          <View style={styles.icon}>
            <Ionicons name="restaurant-outline" size={15} color={Palette.primary} />
          </View>
          <View style={styles.body}>
            <View style={styles.nameRow}>
              <Text style={styles.name}>{dish.name}</Text>
              {dish.local ? <Text style={styles.local}>{dish.local}</Text> : null}
            </View>
            <Text style={styles.note}>{dish.note}</Text>
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Palette.surface,
    borderRadius: Radius.xl,
    padding: Space.lg,
    borderWidth: 1,
    borderColor: Palette.border,
  },
  dish: {
    flexDirection: 'row',
    gap: Space.md,
  },
  divider: {
    marginTop: Space.lg,
    paddingTop: Space.lg,
    borderTopWidth: 1,
    borderTopColor: Palette.borderSoft,
  },
  icon: {
    width: 32,
    height: 32,
    borderRadius: Radius.sm,
    backgroundColor: Palette.primaryTint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  body: {
    flex: 1,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
  },
  name: {
    ...Type.label,
    color: Palette.text,
  },
  local: {
    ...Type.caption,
    color: Palette.primary,
  },
  note: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
    marginTop: 3,
  },
});
