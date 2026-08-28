import { useState } from 'react';
import {
  ActivityIndicator,
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
import { useAuth } from '../../lib/auth';
import { uploadAvatar } from '../../lib/cloudinary';
import { Palette, Radius, Shadow, Space, Type } from '../../constants/trip-theme';

function InfoRow({ icon, text }: { icon: keyof typeof Ionicons.glyphMap; text: string }) {
  return (
    <View style={styles.factRow}>
      <Ionicons name={icon} size={15} color={Palette.textMuted} />
      <Text style={styles.factText}>{text}</Text>
      <Ionicons name="chevron-forward" size={14} color={Palette.textDim} />
    </View>
  );
}

export function ProfileOverview({ travelPoints }: { travelPoints: number }) {
  const auth = useAuth();
  const u = auth.user!;

  const [avatarBusy, setAvatarBusy] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const [signingOut, setSigningOut] = useState(false);

  const [renaming, setRenaming] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [renameBusy, setRenameBusy] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);

  const [changingPw, setChangingPw] = useState(false);
  const [pwSent, setPwSent] = useState(false);
  const [pwOtp, setPwOtp] = useState('');
  const [pwNew, setPwNew] = useState('');
  const [pwBusy, setPwBusy] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwNotice, setPwNotice] = useState<string | null>(null);

  const showDevOtp = (devOtp?: string | null) =>
    devOtp ? ` DEV MODE (no SMTP configured): your code is ${devOtp}.` : '';

  const changePhoto = async () => {
    setAvatarError(null);
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

  const openRename = () => {
    setNewUsername(u.username);
    setRenameError(null);
    setRenaming(true);
  };

  const confirmRename = async () => {
    const trimmed = newUsername.trim().toLowerCase();
    if (trimmed === u.username) {
      setRenaming(false);
      return;
    }
    setRenameBusy(true);
    setRenameError(null);
    try {
      await auth.updateUsername(trimmed);
      setRenaming(false);
    } catch (e) {
      setRenameError(e instanceof Error ? e.message : 'Could not change the username.');
    } finally {
      setRenameBusy(false);
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
      setTimeout(() => setChangingPw(false), 900);
    } catch (e) {
      setPwError(e instanceof Error ? e.message : 'Could not change the password.');
    } finally {
      setPwBusy(false);
    }
  };

  const signOut = async () => {
    setSigningOut(true);
    try {
      await auth.logout();
    } finally {
      setSigningOut(false);
    }
  };

  const joined = new Date(u.created_at);

  return (
    <View style={styles.card}>
      <View style={styles.topRow}>
        <View style={styles.identity}>
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
          <View style={styles.nameBlock}>
            <Text style={styles.name}>{u.full_name}</Text>
            <View style={styles.usernameRow}>
              <Text style={styles.username}>@{u.username}</Text>
              <Pressable onPress={openRename} hitSlop={8} accessibilityLabel="Change username">
                <Ionicons name="create-outline" size={13} color={Palette.textMuted} />
              </Pressable>
            </View>
          </View>
        </View>

        <View style={styles.pointsChip}>
          <View style={styles.pointsBadge}>
            <Ionicons name="star" size={13} color={Palette.primary} />
          </View>
          <View>
            <Text style={styles.pointsValue}>{travelPoints.toLocaleString()}</Text>
            <Text style={styles.pointsLabel}>Travel Points</Text>
          </View>
          <Ionicons name="chevron-forward" size={13} color={Palette.textMuted} />
        </View>
      </View>

      {u.email_verified ? (
        <View style={styles.verifiedPill}>
          <Ionicons name="checkmark-circle" size={13} color={Palette.primary} />
          <Text style={styles.verifiedText}>Verified member</Text>
        </View>
      ) : null}

      {avatarError ? (
        <View style={styles.errorBox}>
          <Ionicons name="alert-circle-outline" size={14} color={Palette.danger} />
          <Text style={styles.errorText}>{avatarError}</Text>
        </View>
      ) : null}

      <View style={styles.divider} />

      <InfoRow icon="mail-outline" text={u.email} />
      <InfoRow icon="location-outline" text={u.country} />
      <InfoRow
        icon="calendar-outline"
        text={`Member since ${joined.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}`}
      />

      <View style={styles.divider} />

      <View style={styles.actionsRow}>
        <Pressable style={styles.changePwBtn} onPress={openChangePassword}>
          <Ionicons name="lock-closed-outline" size={15} color={Palette.primaryDeep} />
          <Text style={styles.changePwText}>Change password</Text>
          <Ionicons name="chevron-forward" size={13} color={Palette.primaryDeep} />
        </Pressable>
        <Pressable style={styles.signOutBtn} onPress={signOut} disabled={signingOut}>
          {signingOut ? (
            <ActivityIndicator size="small" color={Palette.danger} />
          ) : (
            <Ionicons name="log-out-outline" size={15} color={Palette.danger} />
          )}
          <Text style={styles.signOutText}>Sign out</Text>
        </Pressable>
      </View>

      {/* ── change username sheet ───────────────────────────────────────── */}
      <Modal
        visible={renaming}
        transparent
        animationType="slide"
        onRequestClose={() => setRenaming(false)}
      >
        <View style={styles.sheetScrim}>
          <View style={styles.sheet}>
            <View style={styles.sheetHead}>
              <Text style={styles.sheetTitle}>Change username</Text>
              <Pressable onPress={() => setRenaming(false)} hitSlop={10}>
                <Ionicons name="close" size={20} color={Palette.textMuted} />
              </Pressable>
            </View>

            <Text style={styles.hint}>
              3-20 characters: letters, numbers, and underscore. Other travellers see this on
              your ground reports.
            </Text>

            {renameError ? (
              <View style={styles.errorBox}>
                <Ionicons name="alert-circle-outline" size={14} color={Palette.danger} />
                <Text style={styles.errorText}>{renameError}</Text>
              </View>
            ) : null}

            <TextInput
              style={styles.input}
              value={newUsername}
              onChangeText={setNewUsername}
              placeholder="username"
              placeholderTextColor={Palette.textDim}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <Pressable
              style={[styles.primary, renameBusy && styles.primaryBusy]}
              onPress={confirmRename}
              disabled={renameBusy || newUsername.trim().length < 3}
            >
              {renameBusy ? <ActivityIndicator size="small" color={Palette.onDark} /> : null}
              <Text style={styles.primaryText}>Save username</Text>
            </Pressable>
          </View>
        </View>
      </Modal>

      {/* ── change password sheet ───────────────────────────────────────── */}
      <Modal
        visible={changingPw}
        transparent
        animationType="slide"
        onRequestClose={() => setChangingPw(false)}
      >
        <View style={styles.sheetScrim}>
          <View style={styles.sheet}>
            <View style={styles.sheetHead}>
              <Text style={styles.sheetTitle}>Change password</Text>
              <Pressable onPress={() => setChangingPw(false)} hitSlop={10}>
                <Ionicons name="close" size={20} color={Palette.textMuted} />
              </Pressable>
            </View>

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
    padding: Space.lg,
    ...Shadow.card,
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Space.md,
  },
  identity: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.md,
    flexShrink: 1,
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: Radius.pill,
    backgroundColor: Palette.primaryDeep,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarImg: {
    width: 56,
    height: 56,
    borderRadius: Radius.pill,
  },
  avatarText: {
    ...Type.title,
    fontSize: 22,
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
  nameBlock: { flexShrink: 1 },
  name: {
    ...Type.title,
    fontSize: 19,
    color: Palette.text,
  },
  usernameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginTop: 2,
  },
  username: {
    ...Type.label,
    fontSize: 13,
    color: Palette.primary,
  },
  pointsChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: Palette.primaryTint,
    borderRadius: Radius.lg,
    paddingVertical: 8,
    paddingHorizontal: Space.sm,
  },
  pointsBadge: {
    width: 26,
    height: 26,
    borderRadius: Radius.pill,
    backgroundColor: Palette.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pointsValue: {
    ...Type.title,
    fontSize: 16,
    color: Palette.text,
  },
  pointsLabel: {
    ...Type.caption,
    fontSize: 9,
    color: Palette.textMuted,
  },
  verifiedPill: {
    flexDirection: 'row',
    alignSelf: 'flex-start',
    alignItems: 'center',
    gap: 4,
    backgroundColor: Palette.primaryTint,
    borderRadius: Radius.pill,
    paddingHorizontal: Space.sm,
    paddingVertical: 4,
    marginTop: Space.sm,
  },
  verifiedText: {
    ...Type.caption,
    fontSize: 10,
    color: Palette.primaryDeep,
  },
  errorBox: {
    flexDirection: 'row',
    gap: 6,
    alignItems: 'flex-start',
    backgroundColor: Palette.dangerSoft,
    borderRadius: Radius.md,
    padding: Space.md,
    marginTop: Space.md,
  },
  errorText: {
    ...Type.caption,
    color: '#7E2A20',
    flex: 1,
    lineHeight: 15,
  },
  divider: {
    height: 1,
    backgroundColor: Palette.borderSoft,
    marginVertical: Space.md,
  },
  factRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    paddingVertical: Space.sm,
  },
  factText: {
    ...Type.body,
    fontSize: 13,
    color: Palette.text,
    flex: 1,
  },
  actionsRow: {
    flexDirection: 'row',
    gap: Space.sm,
  },
  changePwBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: Space.md,
    borderRadius: Radius.md,
    backgroundColor: Palette.primaryTint,
  },
  changePwText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.primaryDeep,
  },
  signOutBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: Space.md,
    borderRadius: Radius.md,
    backgroundColor: Palette.dangerSoft,
  },
  signOutText: {
    ...Type.label,
    fontSize: 12,
    color: Palette.danger,
  },
  sheetScrim: {
    flex: 1,
    backgroundColor: 'rgba(9, 34, 38, 0.45)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: Palette.surface,
    borderTopLeftRadius: Radius.xxl,
    borderTopRightRadius: Radius.xxl,
    paddingHorizontal: Space.xl,
    paddingBottom: Space.xxl,
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
  hint: {
    ...Type.body,
    fontSize: 12,
    color: Palette.textMuted,
    lineHeight: 17,
    marginTop: Space.md,
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
  primaryBusy: { opacity: 0.8 },
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
});
