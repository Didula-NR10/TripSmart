/**
 * lib/config.ts — app-wide constants that used to live in .env.
 *
 * No more environment variables: edit this file directly to point the app at
 * a different backend.
 *
 * Uses the PC's LAN IP (not "localhost") on purpose: the backend is started
 * with `--host 0.0.0.0`, so this one address answers both from the PC itself
 * (web/browser testing) AND from a phone running the built APK on the same
 * Wi-Fi — "localhost" only works for the former, since on a phone it means
 * the phone itself. One value, both scenarios, no rebuild needed to switch.
 *
 * If your PC's LAN IP changes (new Wi-Fi network, router reassigns it via
 * DHCP), find the new one with `ipconfig` and update it here.
 */
export const API_BASE_URL = 'http://10.44.191.220:8000';