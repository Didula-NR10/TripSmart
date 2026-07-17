/**
 * AuthPanel — the whole account UI on the Profile tab.
 *
 * Logged out: login / signup / verify-OTP / forgot / reset forms.
 * Logged in:  the profile card with a sign-out button.
 */
import { useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Image,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { countries } from '../../constants/countries';
import { useAuth } from '../../lib/auth';
import { cloudinaryConfigured, uploadAvatar } from '../../lib/cloudinary';
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
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);

  // change-password (logged in) — separate state so it never collides with
  // the logged-out forgot/reset fields above.
  const [changingPw, setChangingPw] = useState(false);
  const [pwSent, setPwSent] = useState(false);
  const [pwOtp, setPwOtp] = useState('');
  const [pwNew, setPwNew] = useState('');
  const [pwBusy, setPwBusy] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwNotice, setPwNotice] = useState<string | null>(null);

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

  // Pick an image, push it to Cloudinary, store the URL on the account.
  const changePhoto = async () => {
    setAvatarError(null);
    if (!cloudinaryConfigured()) {
      setAvatarError(
        'Cloudinary is not configured yet. Add EXPO_PUBLIC_CLOUDINARY_CLOUD_NAME and ' +
          'EXPO_PUBLIC_CLOUDINARY_UPLOAD_PRESET to Frontend/.env (see the comments there), ' +
          'then restart Expo.',
      );
      return;
    }
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      setAvatarError('Photo permission denied.');
      return;
    }
    const picked = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.8,
      base64: true,
    });
    if (picked.canceled || !picked.assets?.[0]?.base64) return;

    const asset = picked.assets[0];
    setAvatarBusy(true);
    try {
      const url = await uploadAvatar(
        `data:${asset.mimeType ?? 'image/jpeg'};base64,${asset.base64}`,
      );
      await auth.setAvatar(url);
    } catch (e) {
      setAvatarError(e instanceof Error ? e.message : 'Upload failed.');
    } finally {
      setAvatarBusy(false);
    }
  };

  const openChangePassword = () => {
    setChangingPw(true);
    setPwSent(false);
    setPwOtp('');
    setPwNew('');
    setPwError(null);
    setPwNotice(null);
  };

  const sendPwCode = async () => {
    setPwBusy(true);
    setPwError(null);
    try {
      const r = await auth.changePasswordRequest();
      setPwNotice(`${r.message}${showDevOtp(r.dev_otp)}`);
      setPwSent(true);
    } catch (e) {
      setPwError(e instanceof Error ? e.message : 'Could not send the code.');
    } finally {
      setPwBusy(false);
    }
  };

  const confirmPwChange = async () => {
    setPwBusy(true);
    setPwError(null);
    try {
      const r = await auth.changePasswordConfirm(pwOtp.trim(), pwNew);
      setPwNotice(r.message);
      setChangingPw(false);
      setPwOtp('');
      setPwNew('');
    } catch (e) {
      setPwError(e instanceof Error ? e.message : 'Could not change the password.');
    } finally {
      setPwBusy(false);
    }
  };

  // ── logged in: the profile card ─────────────────────────────────────────
  if (auth.user) {
    const u = auth.user;
    const joined = new Date(u.created_at);
    return (
      <View style={styles.card}>
        <View style={styles.profileHead}>
          <Pressable style={styles.avatar} onPress={changePhoto} disabled={avatarBusy}>
            {u.avatar_url ? (
              <Image source={{ uri: u.avatar_url }} style={styles.avatarImg} />
            ) : (
              <Text style={styles.avatarText}>{u.full_name.slice(0, 1).toUpperCase()}</Text>
            )}
            <View style={styles.camBadge}>
              {avatarBusy ? (
                <ActivityIndicator size={10} color={Palette.onDark} />
              ) : (
                <Ionicons name="camera" size={11} color={Palette.onDark} />
              )}
            </View>
          </Pressable>
          <View style={styles.profileBody}>
            <Text style={styles.profileName}>{u.full_name}</Text>
            <Text style={styles.profileMeta}>@{u.username}</Text>
            <Text style={styles.avatarHint}>Tap the picture to change it</Text>
          </View>
          <View style={styles.verified}>
            <Ionicons name="checkmark-circle" size={13} color={Palette.primary} />
            <Text style={styles.verifiedText}>Verified</Text>
          </View>
        </View>

        {avatarError ? (
          <View style={styles.errorBox}>
            <Ionicons name="alert-circle-outline" size={14} color={Palette.danger} />
            <Text style={styles.errorText}>{avatarError}</Text>
          </View>
        ) : null}

        <View style={styles.factRow}>
          <Ionicons name="mail-outline" size={14} color={Palette.textMuted} />
          <Text style={styles.factText}>{u.email}</Text>
        </View>
        <View style={styles.factRow}>
          <Ionicons name="globe-outline" size={14} color={Palette.textMuted} />
          <Text style={styles.factText}>{u.country}</Text>
        </View>
        <View style={styles.factRow}>
          <Ionicons name="calendar-outline" size={14} color={Palette.textMuted} />
          <Text style={styles.factText}>
            Member since{' '}
            {joined.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}
          </Text>
        </View>

        {/* ── change password ─────────────────────────────────────────── */}
        {!changingPw ? (
          <Pressable style={styles.changePw} onPress={openChangePassword}>
            <Ionicons name="key-outline" size={15} color={Palette.text} />
            <Text style={styles.changePwText}>Change password</Text>
            <Ionicons name="chevron-forward" size={14} color={Palette.textMuted} />
          </Pressable>
        ) : (
          <View style={styles.pwBox}>
            <Text style={styles.hint}>
              {pwSent
                ? `Enter the code sent to ${u.email} and choose a new password.`
                : `We'll email a confirmation code to ${u.email} before changing anything.`}
            </Text>

            {pwNotice ? (
              <View style={styles.notice}>
                <Ionicons name="mail-unread-outline" size={14} color={Palette.primaryDeep} />
                <Text style={styles.noticeText}>{pwNotice}</Text>
              </View>
            ) : null}
            {pwError ? (
              <View style={styles.errorBox}>
                <Ionicons name="alert-circle-outline" size={14} color={Palette.danger} />
                <Text style={styles.errorText}>{pwError}</Text>
              </View>
            ) : null}

            {pwSent ? (
              <>
                <TextInput
                  style={styles.input}
                  value={pwOtp}
                  onChangeText={setPwOtp}
                  placeholder="6-digit code"
                  placeholderTextColor={Palette.textDim}
                  keyboardType="number-pad"
                />
                <TextInput
                  style={styles.input}
                  value={pwNew}
                  onChangeText={setPwNew}
                  placeholder="New password (min 8 characters)"
                  placeholderTextColor={Palette.textDim}
                  secureTextEntry
                  autoCapitalize="none"
                />
                <Pressable
                  style={[styles.primary, pwBusy && styles.primaryBusy]}
                  onPress={confirmPwChange}
                  disabled={pwBusy || pwOtp.trim().length !== 6 || pwNew.length < 8}
                >
                  {pwBusy ? <ActivityIndicator size="small" color={Palette.onDark} /> : null}
                  <Text style={styles.primaryText}>Confirm new password</Text>
                </Pressable>
                <Pressable onPress={sendPwCode} disabled={pwBusy}>
                  <Text style={styles.link}>Resend code</Text>
                </Pressable>
              </>
            ) : (
              <Pressable
                style={[styles.primary, pwBusy && styles.primaryBusy]}
                onPress={sendPwCode}
                disabled={pwBusy}
              >
                {pwBusy ? <ActivityIndicator size="small" color={Palette.onDark} /> : null}
                <Text style={styles.primaryText}>Send confirmation code</Text>
              </Pressable>
            )}

            <Pressable onPress={() => setChangingPw(false)} disabled={pwBusy}>
              <Text style={styles.link}>Cancel</Text>
            </Pressable>
          </View>
        )}

        <Pressable
          style={styles.signOut}
          onPress={() => run(async () => auth.logout())}
          disabled={busy}
        >
          {busy ? (
            <ActivityIndicator size="small" color={Palette.danger} />
          ) : (
            <Ionicons name="log-out-outline" size={16} color={Palette.danger} />
          )}
          <Text style={styles.signOutText}>Sign out</Text>
        </Pressable>
      </View>
    );
  }

  // ── logged out: the forms ───────────────────────────────────────────────
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
  // profile card
  profileHead: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    marginBottom: Space.lg,
  },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: Radius.pill,
    backgroundColor: Palette.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarImg: {
    width: 52,
    height: 52,
    borderRadius: Radius.pill,
  },
  avatarText: {
    ...Type.title,
    color: Palette.onDark,
  },
  camBadge: {
    position: 'absolute',
    right: -2,
    bottom: -2,
    width: 20,
    height: 20,
    borderRadius: Radius.pill,
    backgroundColor: Palette.primaryDeep,
    borderWidth: 2,
    borderColor: Palette.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarHint: {
    ...Type.caption,
    fontSize: 9,
    color: Palette.textDim,
    marginTop: 2,
  },
  profileBody: { flex: 1 },
  profileName: {
    ...Type.title,
    fontSize: 16,
    color: Palette.text,
  },
  profileMeta: {
    ...Type.caption,
    color: Palette.textMuted,
    marginTop: 2,
  },
  verified: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    backgroundColor: Palette.primaryTint,
    borderRadius: Radius.pill,
    paddingHorizontal: Space.sm,
    paddingVertical: 4,
  },
  verifiedText: {
    ...Type.caption,
    fontSize: 9,
    color: Palette.primaryDeep,
  },
  factRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    paddingVertical: Space.sm,
  },
  factText: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
  },
  changePw: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    marginTop: Space.lg,
    paddingVertical: Space.md,
    paddingHorizontal: Space.md,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Palette.border,
    backgroundColor: Palette.canvas,
  },
  changePwText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.text,
    flex: 1,
  },
  pwBox: {
    marginTop: Space.lg,
    paddingTop: Space.lg,
    borderTopWidth: 1,
    borderTopColor: Palette.borderSoft,
  },
  signOut: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Space.sm,
    marginTop: Space.lg,
    paddingVertical: Space.md,
    borderRadius: Radius.md,
    backgroundColor: Palette.dangerSoft,
  },
  signOutText: {
    ...Type.label,
    color: Palette.danger,
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
