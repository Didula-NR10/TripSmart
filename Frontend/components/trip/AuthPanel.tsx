/**
 * AuthPanel — the logged-out account UI on the Profile tab: login / signup /
 * verify-OTP / forgot / reset forms. Once logged in, ProfileOverview takes
 * over (avatar, account facts, change password, sign out).
 */
import { useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { countries } from '../../constants/countries';
import { useAuth } from '../../lib/auth';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

type Mode = 'login' | 'signup' | 'verify' | 'forgot' | 'reset';

export function AuthPanel() {
  const auth = useAuth();
  const [mode, setMode] = useState<Mode>('login');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // form fields
  const [fullName, setFullName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [country, setCountry] = useState('');
  const [password, setPassword] = useState('');
  const [identifier, setIdentifier] = useState('');
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [pickingCountry, setPickingCountry] = useState(false);
  const [countryQuery, setCountryQuery] = useState('');

  const switchMode = (m: Mode) => {
    setMode(m);
    setError(null);
    setNotice(null);
    setOtp('');
  };

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.');
    } finally {
      setBusy(false);
    }
  };

  const showDevOtp = (devOtp?: string | null) =>
    devOtp ? ` DEV MODE (no SMTP configured): your code is ${devOtp}.` : '';

  // ── the forms ────────────────────────────────────────────────────────────
  const field = (
    value: string,
    set: (v: string) => void,
    placeholder: string,
    opts: { secure?: boolean; keyboard?: 'email-address' | 'number-pad' } = {},
  ) => (
    <TextInput
      style={styles.input}
      value={value}
      onChangeText={set}
      placeholder={placeholder}
      placeholderTextColor={Palette.textDim}
      autoCapitalize="none"
      secureTextEntry={opts.secure}
      keyboardType={opts.keyboard}
    />
  );

  const primary = (label: string, onPress: () => void) => (
    <Pressable style={[styles.primary, busy && styles.primaryBusy]} onPress={onPress} disabled={busy}>
      {busy ? <ActivityIndicator size="small" color={Palette.onDark} /> : null}
      <Text style={styles.primaryText}>{label}</Text>
    </Pressable>
  );

  const countryList = countries.filter((c) =>
    c.toLowerCase().includes(countryQuery.trim().toLowerCase()),
  );

  return (
    <View style={styles.card}>
      {/* mode switch */}
      <View style={styles.tabs}>
        <Pressable
          style={[styles.tab, mode === 'login' && styles.tabOn]}
          onPress={() => switchMode('login')}
        >
          <Text style={[styles.tabText, mode === 'login' && styles.tabTextOn]}>Log in</Text>
        </Pressable>
        <Pressable
          style={[styles.tab, mode !== 'login' && styles.tabOn]}
          onPress={() => switchMode('signup')}
        >
          <Text style={[styles.tabText, mode !== 'login' && styles.tabTextOn]}>Sign up</Text>
        </Pressable>
      </View>

      {notice ? (
        <View style={styles.notice}>
          <Ionicons name="mail-unread-outline" size={14} color={Palette.primaryDeep} />
          <Text style={styles.noticeText}>{notice}</Text>
        </View>
      ) : null}
      {error ? (
        <View style={styles.errorBox}>
          <Ionicons name="alert-circle-outline" size={14} color={Palette.danger} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      {mode === 'login' ? (
        <>
          {field(identifier, setIdentifier, 'Username or email')}
          {field(password, setPassword, 'Password', { secure: true })}
          {primary('Log in', () =>
            run(async () => {
              await auth.login(identifier, password);
            }),
          )}
          <Pressable onPress={() => switchMode('forgot')}>
            <Text style={styles.link}>Forgot password?</Text>
          </Pressable>
        </>
      ) : null}

      {mode === 'signup' ? (
        <>
          {field(fullName, setFullName, 'Full name')}
          {field(username, setUsername, 'Username (letters, numbers, _)')}
          {field(email, setEmail, 'Email address', { keyboard: 'email-address' })}
          <Pressable style={styles.select} onPress={() => setPickingCountry(true)}>
            <Ionicons name="globe-outline" size={15} color={Palette.textMuted} />
            <Text style={[styles.selectText, !country && styles.selectPlaceholder]}>
              {country || 'Country'}
            </Text>
            <Ionicons name="chevron-down" size={15} color={Palette.textMuted} />
          </Pressable>
          {field(password, setPassword, 'Password (min 8 characters)', { secure: true })}
          {primary('Create account', () =>
            run(async () => {
              if (!country) throw new Error('Pick your country.');
              const r = await auth.signup({ fullName, username, email, country, password });
              setNotice(`${r.message}${showDevOtp(r.dev_otp)}`);
              setMode('verify');
            }),
          )}
        </>
      ) : null}

      {mode === 'verify' ? (
        <>
          <Text style={styles.hint}>
            Enter the 6-digit code emailed to {email || 'your address'}.
          </Text>
          {email ? null : field(email, setEmail, 'Email address', { keyboard: 'email-address' })}
          {field(otp, setOtp, '6-digit code', { keyboard: 'number-pad' })}
          {primary('Verify & log in', () =>
            run(async () => {
              await auth.verifyEmail(email, otp.trim());
            }),
          )}
          <Pressable
            onPress={() =>
              run(async () => {
                const r = await auth.resendOtp(email, 'signup');
                setNotice(`${r.message}${showDevOtp(r.dev_otp)}`);
              })
            }
          >
            <Text style={styles.link}>Resend code</Text>
          </Pressable>
        </>
      ) : null}

      {mode === 'forgot' ? (
        <>
          <Text style={styles.hint}>
            Enter your account email — a reset code will be sent there.
          </Text>
          {field(email, setEmail, 'Email address', { keyboard: 'email-address' })}
          {primary('Send reset code', () =>
            run(async () => {
              const r = await auth.forgotPassword(email);
              setNotice(`${r.message}${showDevOtp(r.dev_otp)}`);
              setMode('reset');
            }),
          )}
          <Pressable onPress={() => switchMode('login')}>
            <Text style={styles.link}>Back to log in</Text>
          </Pressable>
        </>
      ) : null}

      {mode === 'reset' ? (
        <>
          <Text style={styles.hint}>
            Enter the code sent to {email || 'your email'} and choose a new password.
          </Text>
          {field(otp, setOtp, '6-digit code', { keyboard: 'number-pad' })}
          {field(newPassword, setNewPassword, 'New password (min 8 characters)', { secure: true })}
          {primary('Change password', () =>
            run(async () => {
              const r = await auth.resetPassword(email, otp.trim(), newPassword);
              setNotice(r.message);
              setPassword('');
              setMode('login');
            }),
          )}
          <Pressable
            onPress={() =>
              run(async () => {
                const r = await auth.resendOtp(email, 'reset');
                setNotice(`${r.message}${showDevOtp(r.dev_otp)}`);
              })
            }
          >
            <Text style={styles.link}>Resend code</Text>
          </Pressable>
        </>
      ) : null}

      {/* ── country picker ──────────────────────────────────────────────── */}
      <Modal
        visible={pickingCountry}
        transparent
        animationType="slide"
        onRequestClose={() => setPickingCountry(false)}
      >
        <View style={styles.sheetScrim}>
          <View style={styles.sheet}>
            <View style={styles.sheetHead}>
              <Text style={styles.sheetTitle}>Select your country</Text>
              <Pressable onPress={() => setPickingCountry(false)} hitSlop={10}>
                <Ionicons name="close" size={20} color={Palette.textMuted} />
              </Pressable>
            </View>
            <View style={styles.search}>
              <Ionicons name="search" size={15} color={Palette.textDim} />
              <TextInput
                value={countryQuery}
                onChangeText={setCountryQuery}
                placeholder={`Search ${countries.length} countries`}
                placeholderTextColor={Palette.textDim}
                style={styles.searchInput}
              />
            </View>
            <FlatList
              data={countryList}
              keyExtractor={(c) => c}
              keyboardShouldPersistTaps="handled"
              renderItem={({ item }) => (
                <Pressable
                  style={styles.countryRow}
                  onPress={() => {
                    setCountry(item);
                    setCountryQuery('');
                    setPickingCountry(false);
                  }}
                >
                  <Text style={styles.countryText}>{item}</Text>
                  {item === country ? (
                    <Ionicons name="checkmark" size={16} color={Palette.primary} />
                  ) : null}
                </Pressable>
              )}
            />
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Palette.surface,
    borderRadius: Radius.xl,
    borderWidth: 1,
    borderColor: Palette.border,
    padding: Space.lg,
  },
  tabs: {
    flexDirection: 'row',
    backgroundColor: Palette.canvas,
    borderRadius: Radius.md,
    padding: 3,
    marginBottom: Space.lg,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: Space.sm,
    borderRadius: Radius.sm,
  },
  tabOn: {
    backgroundColor: Palette.surface,
  },
  tabText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.textMuted,
  },
  tabTextOn: {
    color: Palette.text,
  },
  input: {
    ...Type.body,
    fontSize: 13,
    color: Palette.text,
    backgroundColor: Palette.canvas,
    borderWidth: 1,
    borderColor: Palette.border,
    borderRadius: Radius.md,
    paddingHorizontal: Space.md,
    paddingVertical: Space.md,
    marginBottom: Space.sm,
  },
  select: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    backgroundColor: Palette.canvas,
    borderWidth: 1,
    borderColor: Palette.border,
    borderRadius: Radius.md,
    paddingHorizontal: Space.md,
    paddingVertical: Space.md,
    marginBottom: Space.sm,
  },
  selectText: {
    ...Type.body,
    fontSize: 13,
    color: Palette.text,
    flex: 1,
  },
  selectPlaceholder: {
    color: Palette.textDim,
  },
  primary: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Space.sm,
    backgroundColor: Palette.primary,
    borderRadius: Radius.md,
    paddingVertical: Space.md,
    marginTop: Space.xs,
  },
  primaryBusy: {
    opacity: 0.8,
  },
  primaryText: {
    ...Type.label,
    color: Palette.onDark,
  },
  link: {
    ...Type.label,
    fontSize: 12,
    color: Palette.primary,
    textAlign: 'center',
    paddingVertical: Space.md,
  },
  hint: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
    lineHeight: 17,
    marginBottom: Space.md,
  },
  notice: {
    flexDirection: 'row',
    gap: 6,
    alignItems: 'flex-start',
    backgroundColor: Palette.primaryTint,
    borderRadius: Radius.md,
    padding: Space.md,
    marginBottom: Space.md,
  },
  noticeText: {
    ...Type.caption,
    color: Palette.primaryDeep,
    flex: 1,
    lineHeight: 15,
  },
  errorBox: {
    flexDirection: 'row',
    gap: 6,
    alignItems: 'flex-start',
    backgroundColor: Palette.dangerSoft,
    borderRadius: Radius.md,
    padding: Space.md,
    marginBottom: Space.md,
  },
  errorText: {
    ...Type.caption,
    color: '#7E2A20',
    flex: 1,
    lineHeight: 15,
  },
  // country sheet
  sheetScrim: {
    flex: 1,
    backgroundColor: 'rgba(9, 34, 38, 0.45)',
    justifyContent: 'flex-end',
  },
  sheet: {
    height: '78%',
    backgroundColor: Palette.surface,
    borderTopLeftRadius: Radius.xxl,
    borderTopRightRadius: Radius.xxl,
    paddingHorizontal: Space.xl,
    paddingBottom: Space.xl,
    paddingTop: Space.lg,
  },
  sheetHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sheetTitle: {
    ...Type.title,
    color: Palette.text,
  },
  search: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    backgroundColor: Palette.canvas,
    borderRadius: Radius.md,
    paddingHorizontal: Space.md,
    marginTop: Space.lg,
    marginBottom: Space.sm,
  },
  searchInput: {
    flex: 1,
    height: 42,
    ...Type.body,
    color: Palette.text,
  },
  countryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: Space.md,
    borderBottomWidth: 1,
    borderBottomColor: Palette.borderSoft,
  },
  countryText: {
    ...Type.body,
    fontSize: 13,
    color: Palette.text,
  },
});
