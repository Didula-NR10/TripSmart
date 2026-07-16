import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Palette, Space, Type } from '../../constants/trip-theme';

type Props = {
  title: string;
  action: string;
  onPress?: () => void;
};

export function SectionHeader({ title, action, onPress }: Props) {
  return (
    <View style={styles.row}>
      <Text style={styles.title}>{title}</Text>
      <Pressable style={styles.action} onPress={onPress} hitSlop={8}>
        <Text style={styles.actionText}>{action}</Text>
        <Ionicons name="chevron-forward" size={13} color={Palette.primary} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Space.md,
  },
  title: {
    ...Type.heading,
    color: Palette.text,
  },
  action: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 1,
  },
  actionText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.primary,
  },
});
