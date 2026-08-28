import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { LawEntry, lawsForDistrict } from '../constants/laws';
import { Specialty, specialtiesForDistrict } from '../constants/specialties';
import { districtByKey } from '../constants/districts';
import { fetchGroundReports, subscribeDistrictPush } from './api';

const FACT_INTERVAL_S = 30 * 60;
const MAX_SCHEDULED_FACTS = 16;

let configured = false;
let lastNotifiedDistrict: string | null = null;

const NOTIFICATIONS_PREF_KEY = 'settings:notifications_enabled';

export async function getNotificationsEnabled(): Promise<boolean> {
  try {
    const raw = await AsyncStorage.getItem(NOTIFICATIONS_PREF_KEY);
    return raw === null ? true : raw === '1';
  } catch {
    return true;
  }
}

export async function setNotificationsEnabled(enabled: boolean): Promise<void> {
  try {
    await AsyncStorage.setItem(NOTIFICATIONS_PREF_KEY, enabled ? '1' : '0');
  } catch {
  }
  if (!enabled) {
    try {
      await Notifications.cancelAllScheduledNotificationsAsync();
    } catch {
    }
  }
}

async function ensureSetup(): Promise<boolean> {
  if (Platform.OS === 'web') return false;
  if (!(await getNotificationsEnabled())) return false;
  try {
    if (!configured) {
      Notifications.setNotificationHandler({
        handleNotification: async () => ({
          shouldShowBanner: true,
          shouldShowList: true,
          shouldPlaySound: false,
          shouldSetBadge: false,
        }),
      });
      if (Platform.OS === 'android') {
        await Notifications.setNotificationChannelAsync('district-laws', {
          name: 'Local laws, etiquette & specialties',
          importance: Notifications.AndroidImportance.HIGH,
        });
      }
      configured = true;
    }
    const perms = await Notifications.getPermissionsAsync();
    if (perms.granted) return true;
    const asked = await Notifications.requestPermissionsAsync();
    return asked.granted;
  } catch {
    return false;
  }
}

let cachedPushToken: string | null = null;
let lastSubscribedDistrict: string | null = null;

async function getPushToken(): Promise<string | null> {
  if (cachedPushToken) return cachedPushToken;
  if (Platform.OS === 'web') return null;
  try {
    const projectId = Constants.expoConfig?.extra?.eas?.projectId;
    if (!projectId) return null;
    const { data } = await Notifications.getExpoPushTokenAsync({ projectId });
    cachedPushToken = data;
    return data;
  } catch {
    return null;
  }
}

export async function getCachedPushToken(): Promise<string | null> {
  return getPushToken();
}

export async function subscribeDistrictAlerts(districtKey: string): Promise<void> {
  if (districtKey === lastSubscribedDistrict) return;
  const district = districtByKey(districtKey);
  if (!district) return;

  const osReady = await ensureSetup();
  if (!osReady) return;

  const token = await getPushToken();
  if (!token) return;

  try {
    await subscribeDistrictPush(token, districtKey);
    lastSubscribedDistrict = districtKey;
  } catch {
  }
}

export function initRemoteReportListener(): () => void {
  const sub = Notifications.addNotificationReceivedListener((event) => {
    const data = event.request.content.data as
      | { districtKey?: string; kind?: string; remote?: boolean }
      | undefined;
    if (!data?.remote) return;
    const { title, body } = event.request.content;
    recordNotification({
      kind: 'report',
      title: title ?? 'New ground report',
      body: body ?? '',
      districtKey: data.districtKey ?? '',
      at: Date.now(),
    });
  });
  return () => sub.remove();
}

export type NotificationKind = 'district' | 'report';

export type NotificationEntry = {
  id: string;
  kind: NotificationKind;
  title: string;
  body: string;
  districtKey: string;
  at: number;
  read: boolean;
};

const HISTORY_KEY = 'notify:history';
const MAX_HISTORY = 150;

let historyListeners: Array<(entries: NotificationEntry[]) => void> = [];

export function subscribeNotificationHistory(
  fn: (entries: NotificationEntry[]) => void,
): () => void {
  historyListeners.push(fn);
  return () => {
    historyListeners = historyListeners.filter((l) => l !== fn);
  };
}

async function loadHistory(): Promise<NotificationEntry[]> {
  try {
    const raw = await AsyncStorage.getItem(HISTORY_KEY);
    return raw ? (JSON.parse(raw) as NotificationEntry[]) : [];
  } catch {
    return [];
  }
}

async function saveHistory(entries: NotificationEntry[]): Promise<void> {
  try {
    await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(entries));
  } catch {
  }
  historyListeners.forEach((fn) => fn(entries));
}

async function recordNotification(
  entry: Omit<NotificationEntry, 'id' | 'read'>,
): Promise<void> {
  const current = await loadHistory();
  const withNew: NotificationEntry[] = [
    { ...entry, id: `${entry.at}-${Math.random().toString(36).slice(2, 8)}`, read: false },
    ...current,
  ].slice(0, MAX_HISTORY);
  await saveHistory(withNew);
}

/** Everything notified so far, newest first — for the inbox's initial load. */
export async function getNotificationHistory(): Promise<NotificationEntry[]> {
  return loadHistory();
}

/** Called when the inbox is opened — clears the bell's unread badge. */
export async function markAllNotificationsRead(): Promise<void> {
  const current = await loadHistory();
  if (current.every((e) => e.read)) return;
  await saveHistory(current.map((e) => ({ ...e, read: true })));
}

type Fact = { title: string; body: string };

/**
 * The 30-minute drip feed for a district: specialties and laws alternate, so
 * a visitor gets "try the buffalo curd" and "cover shoulders at temples" in
 * turns. Laws arrive already sorted by severity; the top one is skipped here
 * because the entry notification leads with it.
 */
function buildFactCycle(
  districtName: string,
  laws: LawEntry[],
  specials: Specialty[],
): Fact[] {
  const specialtyFacts: Fact[] = specials.map((s) => ({
    title: `${districtName} specialty: ${s.name}`,
    body: s.notification_text,
  }));
  const lawFacts: Fact[] = laws.slice(1).map((l) => ({
    title: `Local rule — ${districtName}`,
    body: l.explanation ? `${l.title}. ${l.explanation}` : l.title,
  }));

  const cycle: Fact[] = [];
  const rounds = Math.max(specialtyFacts.length, lawFacts.length);
  for (let i = 0; i < rounds && cycle.length < MAX_SCHEDULED_FACTS; i++) {
    if (i < specialtyFacts.length) cycle.push(specialtyFacts[i]);
    if (cycle.length >= MAX_SCHEDULED_FACTS) break;
    if (i < lawFacts.length) cycle.push(lawFacts[i]);
  }
  return cycle;
}

/**
 * Fetches the live (last-24h) ground reports for one district and fires a
 * single immediate notification about THEM ONLY — never reports from a
 * district the user isn't currently in. Silently does nothing when that
 * district has no live reports, so entering a quiet district doesn't spam.
 *
 * The in-app history entry is written regardless of whether a real OS
 * notification could be sent (`osReady`), so the bell's inbox stays useful
 * on web/Expo Go too — only the native banner needs a phone.
 */
async function notifyGroundReportsForDistrict(
  districtKey: string,
  osReady: boolean,
): Promise<void> {
  const district = districtByKey(districtKey);
  if (!district) return;

  let reports;
  try {
    reports = await fetchGroundReports({ districtKey });
  } catch {
    return; // offline / server down — no report notification, not an error
  }
  if (reports.length === 0) return;

  const top = reports[0]; // freshest first, per the API's own ordering
  const title =
    reports.length === 1
      ? `1 ground report in ${district.name}`
      : `${reports.length} ground reports in ${district.name}`;
  const body = `${top.title} — ${top.location}`;

  if (osReady) {
    try {
      await Notifications.scheduleNotificationAsync({
        content: { title, body, data: { districtKey, kind: 'report' } },
        trigger: null,
      });
    } catch {
      // A failed OS notification must never break navigation.
    }
  }

  await recordNotification({ kind: 'report', title, body, districtKey, at: Date.now() });
}

/**
 * Called on every GPS fix that resolves to a district. Consecutive fixes in
 * the same district are no-ops; a new district restarts the whole cycle.
 */
export async function notifyDistrictEntered(districtKey: string): Promise<void> {
  if (districtKey === lastNotifiedDistrict) return;
  const district = districtByKey(districtKey);
  if (!district) return;

  // Real OS notifications need a phone (permission + Android channel); the
  // in-app history below is written regardless, so the bell's inbox works
  // on web/Expo Go too.
  const osReady = await ensureSetup();

  const laws = lawsForDistrict(districtKey);
  const specials = specialtiesForDistrict(districtKey);
  lastNotifiedDistrict = districtKey;

  const entryTitle = `Entering ${district.name} — ${laws.length} rules, ${specials.length} local specialties`;
  const entryBody = laws[0]?.title ?? 'Open the Culture tab to explore this district.';

  if (osReady) {
    try {
      // Leaving a district ends its fact cycle before the new one begins.
      await Notifications.cancelAllScheduledNotificationsAsync();

      await Notifications.scheduleNotificationAsync({
        content: {
          title: entryTitle,
          body: entryBody,
          data: { districtKey, kind: 'district' },
        },
        trigger: null, // immediately
      });

      const facts = buildFactCycle(district.name, laws, specials);
      for (let i = 0; i < facts.length; i++) {
        await Notifications.scheduleNotificationAsync({
          content: { title: facts[i].title, body: facts[i].body, data: { districtKey } },
          trigger: {
            type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
            seconds: FACT_INTERVAL_S * (i + 1),
            repeats: false,
            channelId: Platform.OS === 'android' ? 'district-laws' : undefined,
          },
        });
      }
    } catch {
      // A failed notification must never break navigation.
    }
  }

  await recordNotification({
    kind: 'district',
    title: entryTitle,
    body: entryBody,
    districtKey,
    at: Date.now(),
  });

  // Ground reports are fetched from the server, so they run after (and
  // independently of) the local law/specialty notification above.
  notifyGroundReportsForDistrict(districtKey, osReady);
}
