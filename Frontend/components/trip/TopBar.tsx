import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Palette, Radius, Space, TripFonts } from '../../constants/trip-theme';

export function TopBar() {
  return (
    <View style={styles.row}>
      <Text style={styles.wordmark}>
        TRIP
        <Text style={styles.wordmarkAccent}>SMART</Text>
      </Text>

      <View style={styles.actions}>
        <Pressable style={styles.iconButton} hitSlop={6}>
          <Ionicons name="notifications-outline" size={18} color={Palette.text} />
          <View style={styles.dot} />
        </Pressable>
        <View style={styles.avatar}>
          <Ionicons name="person" size={16} color={Palette.textMuted} />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingBottom: Space.xl,
  },
  wordmark: {
    fontFamily: TripFonts.display,
    fontSize: 19,
    letterSpacing: 0.5,
    color: Palette.text,
  },
  wordmarkAccent: {
    color: Palette.accent,
  },
  actions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
  },
  iconButton: {
    width: 36,
    height: 36,
    borderRadius: Radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Palette.surface,
    borderWidth: 1,
    borderColor: Palette.border,
  },
  dot: {
    position: 'absolute',
    top: 8,
    right: 9,
    width: 6,
    height: 6,
    borderRadius: Radius.pill,
    backgroundColor: Palette.accent,
  },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: Radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Palette.surfaceRaised,
    borderWidth: 1,
    borderColor: Palette.borderSoft,
  },
});
