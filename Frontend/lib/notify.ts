/**
 * lib/notify.ts — location-triggered district notifications.
 *
 * When GPS places the user in a new district:
 *   1. Any facts still scheduled for the previous district are cancelled.
 *   2. An immediate "Entering X" notification fires, led by the district's
 *      most severe rule.
 *   3. One fact — alternating local specialties (food, crafts, gems…) and
 *      laws/customs — is scheduled every 30 minutes. These are OS-level
 *      scheduled notifications, so they land in the phone's notification
 *      panel even if the app is backgrounded.
 * Re-fixes inside the same district are ignored, so the 30-minute cycle keeps
 * its rhythm until the user actually crosses into another district.
 *
 * Everything is guarded so web (where expo-notifications has no support) and
 * denied permissions degrade silently — the Culture tab still shows the same
 * information.
 */
import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import { LawEntry, lawsForDistrict } from '../constants/laws';
import { Specialty, specialtiesForDistrict } from '../constants/specialties';
import { districtByKey } from '../constants/districts';

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
 * Called on every GPS fix that resolves to a district. Consecutive fixes in
 * the same district are no-ops; a new district restarts the whole cycle.
 */
export async function notifyDistrictEntered(districtKey: string): Promise<void> {
  if (districtKey === lastNotifiedDistrict) return;
  const district = districtByKey(districtKey);
  if (!district) return;

  const ok = await ensureSetup();
  if (!ok) return;

  const laws = lawsForDistrict(districtKey);
  const specials = specialtiesForDistrict(districtKey);
  lastNotifiedDistrict = districtKey;

  try {
    // Leaving a district ends its fact cycle before the new one begins.
    await Notifications.cancelAllScheduledNotificationsAsync();

    await Notifications.scheduleNotificationAsync({
      content: {
        title: `Entering ${district.name} — ${laws.length} rules, ${specials.length} local specialties`,
        body: laws[0]?.title ?? 'Open the Culture tab to explore this district.',
        data: { districtKey },
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
