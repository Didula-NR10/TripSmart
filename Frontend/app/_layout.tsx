import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import { Tabs } from 'expo-router';
import { useFonts } from 'expo-font';
import * as SplashScreen from 'expo-splash-screen';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import {
  Roboto_400Regular,
  Roboto_500Medium,
  Roboto_700Bold,
} from '@expo-google-fonts/roboto';
import { Caveat_400Regular, Caveat_700Bold } from '@expo-google-fonts/caveat';
import {
  PlayfairDisplay_600SemiBold,
  PlayfairDisplay_700Bold,
} from '@expo-google-fonts/playfair-display';
import { TripProvider } from '../lib/store';
import { AuthProvider } from '../lib/auth';
import { initRemoteReportListener } from '../lib/notify';
import { Palette, Radius, Type } from '../constants/trip-theme';

SplashScreen.preventAutoHideAsync();

const icons: Record<
  string,
  { active: keyof typeof Ionicons.glyphMap; idle: keyof typeof Ionicons.glyphMap }
> = {
  index: { active: 'sunny', idle: 'sunny-outline' },
  explore: { active: 'business', idle: 'business-outline' },
  plan: { active: 'navigate', idle: 'navigate-outline' },
  reports: { active: 'chatbubbles', idle: 'chatbubbles-outline' },
  profile: { active: 'person', idle: 'person-outline' },
};

export default function RootLayout() {
  const [loaded] = useFonts({
    Roboto: Roboto_400Regular,
    Roboto_500Medium,
    Roboto_700Bold,
    Caveat_400Regular,
    Caveat_700Bold,
    PlayfairDisplay_600SemiBold,
    PlayfairDisplay_700Bold,
  });

  useEffect(() => {
    if (loaded) {
      SplashScreen.hideAsync();
    }
  }, [loaded]);

  useEffect(() => initRemoteReportListener(), []);

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
          <Tabs.Screen name="explore" options={{ title: 'Local Guide' }} />
          <Tabs.Screen name="plan" options={{ title: 'Route Intelligence' }} />
          <Tabs.Screen name="reports" options={{ title: 'Ground Reports' }} />
          <Tabs.Screen name="profile" options={{ title: 'Profile' }} />
          <Tabs.Screen name="saved" options={{ href: null }} />
          <Tabs.Screen name="trips" options={{ href: null }} />
          <Tabs.Screen name="search" options={{ href: null }} />
          <Tabs.Screen name="journal" options={{ href: null }} />
          <Tabs.Screen name="settings" options={{ href: null }} />
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
