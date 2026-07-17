/**
 * lib/auth.tsx — the account layer.
 *
 * AuthProvider holds the logged-in user + bearer token, persists the session
 * in AsyncStorage, and pushes the token into lib/api so data calls carry it.
 * useAuthGate() is how features demand login: `if (!gate()) return;` shows a
 * "sign in required" prompt that routes to the Profile tab.
 */
import {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { API_BASE, setAuthToken } from './api';
import { Palette, Radius, Space, Type } from '../constants/trip-theme';

export type AuthUser = {
  id: string;
  full_name: string;
  username: string;
  email: string;
  country: string;
  avatar_url: string;
  email_verified: boolean;
  created_at: string;
  last_login_at: string | null;
};

type AuthApiResult = { token: string; user: AuthUser };
type MessageResult = { message: string; dev_otp?: string | null };

const SESSION_KEY = 'auth:session';

async function call<T>(
  path: string,
  body?: object,
  token?: string | null,
  method?: 'GET' | 'POST',
): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1/auth/${path}`, {
    method: method ?? (body ? 'POST' : 'GET'),
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail =
      typeof data?.detail === 'string'
        ? data.detail
        : Array.isArray(data?.detail)
          ? data.detail[0]?.msg ?? 'Invalid input.'
          : `Request failed (${res.status}).`;
    throw new Error(detail);
  }
  return data as T;
}

type AuthContextValue = {
  user: AuthUser | null;
  ready: boolean;
  signup: (v: {
    fullName: string;
    username: string;
    email: string;
    country: string;
    password: string;
  }) => Promise<MessageResult>;
  verifyEmail: (email: string, otp: string) => Promise<void>;
  login: (identifier: string, password: string) => Promise<void>;
  forgotPassword: (email: string) => Promise<MessageResult>;
  resetPassword: (email: string, otp: string, newPassword: string) => Promise<MessageResult>;
  resendOtp: (email: string, purpose: 'signup' | 'reset') => Promise<MessageResult>;
  /** Persist a freshly uploaded Cloudinary URL as the profile picture. */
  setAvatar: (avatarUrl: string) => Promise<void>;
  /** Emails a confirmation code to the logged-in user's own address. */
  changePasswordRequest: () => Promise<MessageResult>;
  /** Confirms the code and sets the new password; current session stays logged in. */
  changePasswordConfirm: (otp: string, newPassword: string) => Promise<MessageResult>;
  logout: () => Promise<void>;
  /** Returns true when logged in; otherwise shows the sign-in prompt and returns false. */
  requireAuth: () => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [promptVisible, setPromptVisible] = useState(false);

  // Restore the saved session, then re-validate it against the server.
  useEffect(() => {
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(SESSION_KEY);
        if (raw) {
          const saved = JSON.parse(raw) as { token: string; user: AuthUser };
          setToken(saved.token);
          setUser(saved.user);
          setAuthToken(saved.token);
          // Background check: a revoked/expired token logs the user out.
          call<AuthUser>('me', undefined, saved.token)
            .then((fresh) => setUser(fresh))
            .catch(() => {
              setUser(null);
              setToken(null);
              setAuthToken(null);
              AsyncStorage.removeItem(SESSION_KEY);
            });
        }
      } catch {
        // A corrupt session is just a logged-out state.
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const adopt = useCallback(async (result: AuthApiResult) => {
    setUser(result.user);
    setToken(result.token);
    setAuthToken(result.token);
    await AsyncStorage.setItem(
      SESSION_KEY,
      JSON.stringify({ token: result.token, user: result.user }),
    );
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      ready,
      signup: (v) =>
        call<MessageResult>('signup', {
          full_name: v.fullName,
          username: v.username,
          email: v.email,
          country: v.country,
          password: v.password,
        }),
      verifyEmail: async (email, otp) => {
        await adopt(await call<AuthApiResult>('verify-email', { email, otp }));
      },
      login: async (identifier, password) => {
        await adopt(await call<AuthApiResult>('login', { identifier, password }));
      },
      forgotPassword: (email) => call<MessageResult>('forgot-password', { email }),
      resetPassword: (email, otp, newPassword) =>
        call<MessageResult>('reset-password', { email, otp, new_password: newPassword }),
      resendOtp: (email, purpose) => call<MessageResult>('resend-otp', { email, purpose }),
      setAvatar: async (avatarUrl) => {
        const fresh = await call<AuthUser>('avatar', { avatar_url: avatarUrl }, token);
        setUser(fresh);
        if (token) {
          await AsyncStorage.setItem(SESSION_KEY, JSON.stringify({ token, user: fresh }));
        }
      },
      changePasswordRequest: () =>
        call<MessageResult>('change-password/request', {}, token, 'POST'),
      changePasswordConfirm: (otp, newPassword) =>
        call<MessageResult>(
          'change-password/confirm', { otp, new_password: newPassword }, token,
        ),
      logout: async () => {
        if (token) {
          call('logout', {}, token).catch(() => {});
        }
        setUser(null);
        setToken(null);
        setAuthToken(null);
        await AsyncStorage.removeItem(SESSION_KEY);
      },
      requireAuth: () => {
        if (user) return true;
        setPromptVisible(true);
        return false;
      },
    }),
    [user, ready, token, adopt],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}

      {/* ── the "sign in required" prompt ────────────────────────────── */}
      <Modal
        visible={promptVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setPromptVisible(false)}
      >
        <View style={styles.scrim}>
          <View style={styles.card}>
            <View style={styles.badge}>
              <Ionicons name="lock-closed-outline" size={22} color={Palette.primary} />
            </View>
            <Text style={styles.kind}>SIGN IN REQUIRED</Text>
            <Text style={styles.title}>Log in to continue</Text>
            <Text style={styles.body}>
              Predictions, district comparisons and ground reports need an account, so the
              community knows who is behind each report.
            </Text>
            <Pressable
              style={styles.primary}
              onPress={() => {
                setPromptVisible(false);
                router.push('/profile');
              }}
            >
              <Text style={styles.primaryText}>Log in / Sign up</Text>
            </Pressable>
            <Pressable style={styles.secondary} onPress={() => setPromptVisible(false)}>
              <Text style={styles.secondaryText}>Not now</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

/** The gate: `const gate = useAuthGate(); if (!gate()) return;` */
export function useAuthGate(): () => boolean {
  return useAuth().requireAuth;
}

const styles = StyleSheet.create({
  scrim: {
    flex: 1,
    backgroundColor: 'rgba(9, 34, 38, 0.55)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: Space.xl,
  },
  card: {
    width: '100%',
    maxWidth: 400,
    backgroundColor: Palette.surface,
    borderRadius: Radius.xxl,
    padding: Space.xl,
  },
  badge: {
    width: 52,
    height: 52,
    borderRadius: Radius.lg,
    backgroundColor: Palette.primaryTint,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Space.lg,
  },
  kind: {
    ...Type.eyebrow,
    color: Palette.textMuted,
  },
  title: {
    ...Type.title,
    color: Palette.text,
    marginTop: 4,
  },
  body: {
    ...Type.body,
    color: Palette.textMuted,
    lineHeight: 19,
    marginTop: Space.md,
  },
  primary: {
    marginTop: Space.xl,
    paddingVertical: Space.md,
    borderRadius: Radius.md,
    alignItems: 'center',
    backgroundColor: Palette.primary,
  },
  primaryText: {
    ...Type.label,
    color: Palette.onDark,
  },
  secondary: {
    marginTop: Space.sm,
    paddingVertical: Space.md,
    borderRadius: Radius.md,
    alignItems: 'center',
  },
  secondaryText: {
    ...Type.label,
    color: Palette.textMuted,
  },
});
