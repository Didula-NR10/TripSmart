import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react';
import { ProfileKey } from '../constants/profiles';
import { Prediction, predict } from './engine';
import { Forecast24, cacheForecast, fetchForecastBundle, loadCachedForecast } from './api';
import { subscribeDistrictAlerts } from './notify';

export type ForecastSource = 'live' | 'cache' | 'synthetic';

export type Watch = {
  districtKey: string;
  at: number;
};

type Store = {
  districtKey: string;
  setDistrictKey: (key: string) => void;

  profileKey: ProfileKey;
  setProfileKey: (key: ProfileKey) => void;

  offline: boolean;
  toggleOffline: () => void;

  prediction: Prediction;
  cachedAt: number;
  source: ForecastSource;

  forecast24: Forecast24 | null;
  forecast24Loading: boolean;
  runForecast24: () => Promise<void>;

  watches: Watch[];
  toggleWatch: (districtKey: string) => void;
};

const TripContext = createContext<Store | null>(null);

export function TripProvider({ children }: { children: ReactNode }) {
  const [districtKey, setDistrictKey] = useState('colombo');
  const [profileKey, setProfileKey] = useState<ProfileKey>('sightseer');
  const [offline, setOffline] = useState(false);
  const [watches, setWatches] = useState<Watch[]>([]);

  const [prediction, setPrediction] = useState<Prediction>(() => predict(districtKey));
  const [cachedAt, setCachedAt] = useState<number>(() => Date.now());
  const [source, setSource] = useState<ForecastSource>('synthetic');

  const [forecast24, setForecast24] = useState<Forecast24 | null>(null);
  const [forecast24Loading, setForecast24Loading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const useCached = async () => {
      const cached = await loadCachedForecast(districtKey);
      if (cached && !cancelled) {
        setPrediction(cached.bundle.prediction);
        setForecast24(cached.bundle.live);
        setCachedAt(cached.at);
        setSource('cache');
      }
    };

    setPrediction(predict(districtKey));
    setForecast24(null);
    setCachedAt(Date.now());
    setSource('synthetic');

    if (offline) {
      useCached();
      return () => {
        cancelled = true;
      };
    }

    fetchForecastBundle(districtKey)
      .then((bundle) => {
        if (cancelled) return;
        setPrediction(bundle.prediction);
        setCachedAt(bundle.prediction.generatedAt);
        setSource('live');
        cacheForecast(districtKey, bundle);
      })
      .catch(useCached);

    return () => {
      cancelled = true;
    };
  }, [districtKey, offline]);

  useEffect(() => {
    subscribeDistrictAlerts(districtKey);
  }, [districtKey]);

  const runForecast24 = useCallback(async () => {
    setForecast24Loading(true);
    try {
      const bundle = await fetchForecastBundle(districtKey, { refresh: true });
      setPrediction(bundle.prediction);
      setCachedAt(bundle.prediction.generatedAt);
      setSource('live');
      setForecast24(bundle.live);
      cacheForecast(districtKey, bundle);
    } catch {
      const cached = await loadCachedForecast(districtKey);
      if (cached) {
        setPrediction(cached.bundle.prediction);
        setForecast24(cached.bundle.live);
        setCachedAt(cached.at);
        setSource('cache');
      }
    } finally {
      setForecast24Loading(false);
    }
  }, [districtKey]);

  const toggleWatch = useCallback((key: string) => {
    setWatches((prev) =>
      prev.some((w) => w.districtKey === key)
        ? prev.filter((w) => w.districtKey !== key)
        : [...prev, { districtKey: key, at: Date.now() }],
    );
  }, []);

  const value: Store = {
    districtKey,
    setDistrictKey,
    profileKey,
    setProfileKey,
    offline,
    toggleOffline: () => setOffline((v) => !v),
    prediction,
    cachedAt,
    source,
    forecast24,
    forecast24Loading,
    runForecast24,
    watches,
    toggleWatch,
  };

  return <TripContext.Provider value={value}>{children}</TripContext.Provider>;
}

export function useTrip() {
  const ctx = useContext(TripContext);
  if (!ctx) {
    throw new Error('useTrip must be used inside TripProvider');
  }
  return ctx;
}
