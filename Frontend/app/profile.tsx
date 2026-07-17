import { ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AuthPanel } from '../components/trip/AuthPanel';
import { TravelNotebook } from '../components/trip/TravelNotebook';
import { ScreenTitle, SectionHeader } from '../components/trip/Ui';
import { useAuth } from '../lib/auth';
import { Palette, Space } from '../constants/trip-theme';

export default function ProfileScreen() {
  const { user } = useAuth();

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <ScreenTitle
          title="Profile"
          subtitle={
            user
              ? 'Your account and your travel notebook.'
              : 'Log in or create an account to predict, compare districts and post ground reports.'
          }
        />

        <SectionHeader title="Account" />
        <AuthPanel />

        {user ? (
          <View style={styles.section}>
            <SectionHeader title="Travel notebook" />
            <TravelNotebook />
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Palette.canvas },
  content: { padding: Space.lg, paddingBottom: Space.section },
  section: { marginTop: Space.section },
});
