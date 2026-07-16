import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

type Props = {
  title: string;
  detail: string;
  icon: keyof typeof Ionicons.glyphMap;
};

export function Placeholder({ title, detail, icon }: Props) {
  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.center}>
        <View style={styles.iconWrap}>
          <Ionicons name={icon} size={22} color={Palette.primary} />
        </View>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.detail}>{detail}</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: Palette.canvas,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Space.section,
    gap: Space.md,
  },
  iconWrap: {
    width: 52,
    height: 52,
    borderRadius: Radius.lg,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Palette.primarySoft,
    marginBottom: Space.xs,
  },
  title: {
    ...Type.title,
    color: Palette.text,
  },
  detail: {
    ...Type.body,
    color: Palette.textMuted,
    textAlign: 'center',
  },
});
