/**
 * lib/notify.ts — location-triggered district notifications.
 *
 * When GPS places the user in a new district:
 *   1. Any facts still scheduled for the previous district are cancelled.
 *   2. An immediate "Entering X" notification fires, led by the district's
 *      most severe rule.
 *   3. A second immediate notification fires for that district's live ground
 *      reports ONLY — crossing into another district notifies about that
 *      new district's reports instead, never a mix of two districts.
 *   4. One fact — alternating local specialties (food, crafts, gems…) and
 *      laws/customs — is scheduled every 30 minutes. These are OS-level
 *      scheduled notifications, so they land in the phone's notification
 *      panel even if the app is backgrounded.
 * Re-fixes inside the same district are ignored, so the 30-minute cycle keeps
 * its rhythm until the user actually crosses into another district.
 *
 * Every notification this module fires is also appended to a small in-app
 * history (AsyncStorage) so the bell button can show "what did I just get
 * notified about" even on web/Expo Go, where the OS tray isn't reliable.
 *
 * Everything is guarded so web (where expo-notifications has no support) and
 * denied permissions degrade silently — the Culture tab still shows the same
 * information.
 */
import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { LawEntry, lawsForDistrict } from '../constants/laws';
import { Specialty, specialtiesForDistrict } from '../constants/specialties';
import { districtByKey } from '../constants/districts';
import { fetchGroundReports } from './api';

const FACT_INTERVAL_S = 30 * 60; // one fact per 30 minutes
const MAX_SCHEDULED_FACTS = 16;  // 8 hours of facts; iOS caps pending notifications at 64

let configured = false;
let lastNotifiedDistrict: string | null = null;

async function ensureSetup(): Promise<boolean> {
  if (Platform.OS === 'web') return false;
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

// ── in-app notification history — what the bell button shows ────────────────

export type NotificationKind = 'district' | 'report';

export type NotificationEntry = {
  id: string;
  kind: NotificationKind;
  title: string;
  body: string;
  districtKey: string;
  at: number; // epoch ms, when it fired
  read: boolean;
};

const HISTORY_KEY = 'notify:history';
const MAX_HISTORY = 150;

let historyListeners: Array<(entries: NotificationEntry[]) => void> = [];

/** Subscribe to live history updates (used by the bell badge + inbox). Returns an unsubscribe fn. */
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
    // History is a nice-to-have; losing it must never break notifications.
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
