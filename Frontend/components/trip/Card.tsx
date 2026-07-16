import { StyleSheet, View, ViewProps } from 'react-native';
import { Palette, Radius } from '../../constants/trip-theme';

type Props = ViewProps & {
  inset?: boolean;
};

export function Card({ style, inset, ...rest }: Props) {
  return <View style={[styles.card, inset && styles.inset, style]} {...rest} />;
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Palette.surface,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: Palette.border,
  },
  inset: {
    backgroundColor: Palette.surfaceInset,
  },
});
