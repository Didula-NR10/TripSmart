import React, { useEffect, useMemo, useState } from 'react';
import api from '../lib/api';
import { getErrorMessage } from '../lib/errors';

/**
 * Trip Smart — 24-hour forecast.
 *
 * The model emits three channels (temperature, rainfall, humidity) for the next
 * 24 hours, each already carrying an advisory. This page's job is to make the
 * DECISION obvious before the data is: verdict first, then the shape of the day,
 * then the hour-by-hour detail for anyone who wants to look closer.
 */

const ADVISORY = {
  GOOD: {
    label: 'Good to go',
    dot: 'bg-emerald-500',
    chip: 'bg-emerald-50 text-emerald-700 border-emerald-100',
    hero: 'from-emerald-500 to-emerald-700',
  },
  CAUTION: {
    label: 'Caution',
    dot: 'bg-amber-500',
    chip: 'bg-amber-50 text-amber-700 border-amber-100',
    hero: 'from-amber-500 to-orange-600',
  },
  AVOID: {
    label: 'Avoid travel',
    dot: 'bg-red-500',
    chip: 'bg-red-50 text-red-600 border-red-100',
    hero: 'from-red-500 to-rose-700',
  },
};

const RainIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5" aria-hidden="true">
    <path d="M7 16a4.5 4.5 0 0 1 .9-8.9 5.5 5.5 0 0 1 10.6 1.4A3.5 3.5 0 0 1 18 16H7Z" />
    <path d="M9 19.5 8 21M13 19.5 12 21M17 19.5 16 21" />
  </svg>
);

const TempIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5" aria-hidden="true">
    <path d="M12 14V4a2 2 0 0 1 4 0v10a4 4 0 1 1-4 0Z" />
  </svg>
);

const DropIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5" aria-hidden="true">
    <path d="M12 3s6 6.4 6 10a6 6 0 0 1-12 0c0-3.6 6-10 6-10Z" />
  </svg>
);

/** Hand-rolled SVG so the page needs no charting dependency. */
const ForecastChart = ({ hours }) => {
  const W = 720;
  const H = 190;
  const PAD = { l: 34, r: 12, t: 14, b: 24 };

  const temps = hours.map((h) => h.temperature_c);
  const rains = hours.map((h) => h.precipitation_mm);

  const tMin = Math.floor(Math.min(...temps) - 1);
  const tMax = Math.ceil(Math.max(...temps) + 1);
  const rMax = Math.max(1, Math.ceil(Math.max(...rains) * 1.2));

  const x = (i) => PAD.l + (i * (W - PAD.l - PAD.r)) / (hours.length - 1);
  const yT = (v) => PAD.t + ((tMax - v) / (tMax - tMin)) * (H - PAD.t - PAD.b);
  const yR = (v) => H - PAD.b - (v / rMax) * (H - PAD.t - PAD.b);

  const line = temps.map((v, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${yT(v).toFixed(1)}`).join(' ');
  const area = `${line} L ${x(hours.length - 1)} ${H - PAD.b} L ${x(0)} ${H - PAD.b} Z`;
  const barW = Math.max(3, (W - PAD.l - PAD.r) / hours.length - 3);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="24 hour temperature and rainfall">
      <defs>
        <linearGradient id="tempFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7F0DF2" stopOpacity="0.22" />
          <stop offset="100%" stopColor="#7F0DF2" stopOpacity="0" />
        </linearGradient>
      </defs>

      {[0, 0.5, 1].map((f) => {
        const v = tMin + (tMax - tMin) * (1 - f);
        return (
          <g key={f}>
            <line x1={PAD.l} x2={W - PAD.r} y1={yT(v)} y2={yT(v)} stroke="#7C7482" strokeOpacity="0.12" />
            <text x={4} y={yT(v) + 3} fontSize="9" fill="#7C7482">{Math.round(v)}°</text>
          </g>
        );
      })}

      {/* Rainfall — bars, because rain is discrete and additive */}
      {hours.map((h, i) => (
        h.precipitation_mm > 0 && (
          <rect
            key={h.forecast_hour}
            x={x(i) - barW / 2}
            y={yR(h.precipitation_mm)}
            width={barW}
            height={Math.max(1, H - PAD.b - yR(h.precipitation_mm))}
            rx="1.5"
            fill="#38BDF8"
            fillOpacity="0.55"
          />
        )
      ))}

      {/* Temperature — a continuous curve, because it is one */}
      <path d={area} fill="url(#tempFill)" />
      <path d={line} fill="none" stroke="#7F0DF2" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />

      {hours.map((h, i) => (
        i % 3 === 0 && (
          <text key={h.forecast_hour} x={x(i)} y={H - 6} fontSize="9" fill="#7C7482" textAnchor="middle">
            +{h.forecast_hour}h
          </text>
        )
      ))}
    </svg>
  );
};

const ForecastPage = () => {
  const [districts, setDistricts] = useState([]);
  const [district, setDistrict] = useState('Colombo');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/api/v1/forecast/districts')
      .then((res) => setDistricts(res.data))
      .catch(() => setDistricts([]));
  }, []);

  const load = (name, refresh = false) => {
    setLoading(true);
    setError('');
    api.get(`/api/v1/forecast/${name}`, { params: { refresh } })
      .then((res) => setData(res.data))
      .catch((err) => {
        setData(null);
        setError(getErrorMessage(err, 'Could not produce a forecast for this district.'));
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(district); /* eslint-disable-next-line */ }, [district]);

  const verdict = data ? ADVISORY[data.summary.advisory_level] : ADVISORY.GOOD;
  const worstHours = useMemo(
    () => (data ? data.forecast.filter((h) => h.advisory_level !== 'GOOD') : []),
    [data],
  );

  return (
    <div className="min-h-screen bg-[#F8F6FA] pt-32 pb-24 px-6">
      <div className="max-w-5xl mx-auto">

        <div className="flex flex-col md:flex-row md:items-end justify-between gap-5 mb-8">
          <div>
            <p className="text-[#7F0DF2] text-xs font-extrabold uppercase tracking-widest mb-2">Trip Smart</p>
            <h1 className="text-3xl font-extrabold text-[#140D1C]">Should you travel tomorrow?</h1>
            <p className="text-[#7C7482] mt-2 max-w-lg">
              A 24-hour forecast for any Sri Lankan district, from a model trained on seven days of
              local weather history.
            </p>
          </div>

          <div className="flex gap-2 shrink-0">
            <select
              value={district}
              onChange={(e) => setDistrict(e.target.value)}
              className="bg-white border border-[#7C7482]/15 rounded-full px-5 py-3 text-sm font-bold text-[#140D1C] outline-none focus:border-[#7F0DF2]/50 cursor-pointer"
            >
              {districts.length === 0 && <option>{district}</option>}
              {districts.map((d) => <option key={d.name} value={d.name}>{d.name}</option>)}
            </select>
            <button
              onClick={() => load(district, true)}
              disabled={loading}
              className="bg-white border border-[#7C7482]/15 text-[#140D1C] font-bold text-sm px-5 py-3 rounded-full hover:border-[#7F0DF2]/40 transition disabled:opacity-50"
            >
              {loading ? '…' : 'Refresh'}
            </button>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-2xl px-4 py-3 mb-6">{error}</div>
        )}

        {loading && !data && (
          <div className="bg-white rounded-3xl border border-[#7C7482]/10 p-16 text-center text-[#7C7482]">
            Running the model for {district}…
          </div>
        )}

        {data && (
          <>
            {/* The verdict — the only thing most people need */}
            <div className={`rounded-[2rem] bg-gradient-to-br ${verdict.hero} text-white p-8 mb-6 shadow-[0_20px_50px_-24px_rgba(20,13,28,0.6)]`}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-white/70 text-xs font-extrabold uppercase tracking-[0.14em]">
                    {data.district} · next 24 hours
                  </p>
                  <h2 className="text-3xl font-extrabold mt-2">{data.summary.verdict}</h2>
                  <p className="text-white/80 text-sm mt-2">
                    {data.summary.wet_hours > 0
                      ? `${data.summary.wet_hours} wet hour${data.summary.wet_hours > 1 ? 's' : ''} expected, ${data.summary.total_rain_mm} mm total.`
                      : 'No meaningful rainfall expected.'}
                  </p>
                </div>
                <span className="bg-white/20 backdrop-blur-sm text-[11px] font-extrabold uppercase tracking-[0.12em] px-4 py-2 rounded-full">
                  {verdict.label}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-4 mt-8">
                {[
                  { icon: <TempIcon />, label: 'Temperature', value: `${data.summary.temp_min_c}° – ${data.summary.temp_max_c}°`, sub: `avg ${data.summary.temp_avg_c}°C` },
                  { icon: <RainIcon />, label: 'Rainfall', value: `${data.summary.total_rain_mm} mm`, sub: `${data.summary.wet_hours} wet hours` },
                  { icon: <DropIcon />, label: 'Humidity', value: `${data.summary.humidity_min_pct}–${data.summary.humidity_max_pct}%`, sub: 'range' },
                ].map((stat) => (
                  <div key={stat.label} className="bg-white/10 backdrop-blur-sm rounded-2xl p-4">
                    <span className="text-white/70 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider">
                      {stat.icon} {stat.label}
                    </span>
                    <p className="text-xl font-extrabold mt-2">{stat.value}</p>
                    <p className="text-white/60 text-[11px]">{stat.sub}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* The shape of the day */}
            <div className="bg-white rounded-3xl border border-[#7C7482]/10 p-6 mb-6 shadow-[0_10px_30px_-22px_rgba(20,13,28,0.35)]">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-extrabold text-[#140D1C]">Next 24 hours</h3>
                <div className="flex items-center gap-4 text-[11px] text-[#7C7482]">
                  <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-[#7F0DF2] rounded" /> Temperature</span>
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 bg-[#38BDF8]/60 rounded-sm" /> Rainfall</span>
                </div>
              </div>
              <ForecastChart hours={data.forecast} />
            </div>

            {/* Hours worth worrying about, surfaced rather than buried */}
            {worstHours.length > 0 && (
              <div className="bg-white rounded-3xl border border-[#7C7482]/10 p-6 mb-6">
                <h3 className="font-extrabold text-[#140D1C] mb-4">Hours to plan around</h3>
                <div className="flex flex-wrap gap-2">
                  {worstHours.map((h) => {
                    const a = ADVISORY[h.advisory_level];
                    return (
                      <span key={h.forecast_hour} className={`text-xs font-semibold px-3 py-1.5 rounded-full border ${a.chip}`}>
                        +{h.forecast_hour}h · {h.advisory_reason}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}

            {/* The detail, for anyone who wants it */}
            <div className="bg-white rounded-3xl border border-[#7C7482]/10 overflow-hidden">
              <div className="px-6 py-4 border-b border-[#7C7482]/10 flex items-center justify-between">
                <h3 className="font-extrabold text-[#140D1C]">Hour by hour</h3>
                <span className="text-[11px] text-[#7C7482]">
                  {data.cached ? 'Cached run' : 'Fresh run'} · {new Date(data.forecast_origin).toLocaleString()}
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[11px] font-bold uppercase tracking-wider text-[#7C7482]/80 bg-[#F8F7FA]">
                      <th className="text-left px-6 py-3">Time</th>
                      <th className="text-right px-4 py-3">Temp</th>
                      <th className="text-right px-4 py-3">Rain</th>
                      <th className="text-right px-4 py-3">Humidity</th>
                      <th className="text-left px-6 py-3">Advisory</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.forecast.map((h) => {
                      const a = ADVISORY[h.advisory_level];
                      return (
                        <tr key={h.forecast_hour} className="border-t border-[#7C7482]/8 hover:bg-[#F8F7FA] transition">
                          <td className="px-6 py-3">
                            <span className="font-bold text-[#140D1C]">+{h.forecast_hour}h</span>
                            <span className="text-[#7C7482] text-xs ml-2">{h.valid_time.slice(11)}</span>
                          </td>
                          <td className="px-4 py-3 text-right font-semibold text-[#140D1C]">{h.temperature_c}°C</td>
                          <td className="px-4 py-3 text-right text-[#7C7482]">{h.precipitation_mm} mm</td>
                          <td className="px-4 py-3 text-right text-[#7C7482]">{h.humidity_pct}%</td>
                          <td className="px-6 py-3">
                            <span className="inline-flex items-center gap-2 text-xs font-semibold">
                              <span className={`w-2 h-2 rounded-full ${a.dot}`} />
                              {h.advisory_reason}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default ForecastPage;
