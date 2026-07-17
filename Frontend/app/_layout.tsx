import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import { Tabs } from 'expo-router';
import { useFonts } from 'expo-font';
import * as SplashScreen from 'expo-splash-screen';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  Inter_700Bold,
} from '@expo-google-fonts/inter';
import { TripProvider } from '../lib/store';
import { AuthProvider } from '../lib/auth';
import { Palette, Radius, Type } from '../constants/trip-theme';

SplashScreen.preventAutoHideAsync();

const icons: Record<
  string,
  { active: keyof typeof Ionicons.glyphMap; idle: keyof typeof Ionicons.glyphMap }
> = {
  index: { active: 'sunny', idle: 'sunny-outline' },
  explore: { active: 'shield-checkmark', idle: 'shield-checkmark-outline' },
  plan: { active: 'navigate', idle: 'navigate-outline' },
  reports: { active: 'chatbubbles', idle: 'chatbubbles-outline' },
  profile: { active: 'person', idle: 'person-outline' },
};

export default function RootLayout() {
  const [loaded] = useFonts({
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
    Inter_700Bold,
  });

  useEffect(() => {
    if (loaded) {
      SplashScreen.hideAsync();
    }
  }, [loaded]);

  if (!loaded) {
    return null;
  }

  return (
    <SafeAreaProvider>
      <AuthProvider>
      <TripProvider>
        <Tabs
          screenOptions={({ route }) => ({
            headerShown: false,
            sceneStyle: { backgroundColor: Palette.canvas },
            tabBarActiveTintColor: Palette.primary,
            tabBarInactiveTintColor: Palette.textDim,
            tabBarStyle: {
              backgroundColor: Palette.surface,
              borderTopColor: Palette.border,
              borderTopWidth: 1,
              height: 76,
              paddingTop: 10,
              paddingBottom: 14,
            },
            tabBarLabelStyle: Type.tab,
            tabBarIcon: ({ color, focused }) => {
              const set = icons[route.name] ?? icons.index;
              return (
                <View style={[styles.icon, focused && styles.iconActive]}>
                  <Ionicons name={focused ? set.active : set.idle} size={19} color={color} />
                </View>
              );
            },
          })}
        >
          <Tabs.Screen name="index" options={{ title: 'Forecast' }} />
          <Tabs.Screen name="explore" options={{ title: 'Culture' }} />
          <Tabs.Screen name="plan" options={{ title: 'Router' }} />
          <Tabs.Screen name="reports" options={{ title: 'Ground' }} />
          <Tabs.Screen name="profile" options={{ title: 'Profile' }} />
          <Tabs.Screen name="saved" options={{ href: null }} />
          <Tabs.Screen name="trips" options={{ href: null }} />
          <Tabs.Screen name="search" options={{ href: null }} />
        </Tabs>
      </TripProvider>
      </AuthProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  icon: {
    width: 46,
    height: 30,
    borderRadius: Radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconActive: {
    backgroundColor: Palette.primarySoft,
  },
});
