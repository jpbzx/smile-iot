import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { useChartTheme } from '../theme.js';

const timeTick = (iso) =>
  new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

function useTooltipStyles() {
  const t = useChartTheme();
  return {
    contentStyle: {
      background: t.surface,
      border: `1px solid ${t.border}`,
      borderRadius: 8,
      color: t.ink,
      fontSize: 13,
    },
    labelStyle: { color: t.muted, fontSize: 12 },
    itemStyle: { color: t.ink },
  };
}

function axisProps(t) {
  return {
    stroke: t.axis,
    tick: { fill: t.muted, fontSize: 12 },
    tickLine: false,
  };
}

// Single series → no legend; the card title names it (identity never color-alone).
export function PowerChart({ points }) {
  const t = useChartTheme();
  const tip = useTooltipStyles();
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={points} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={t.grid} vertical={false} />
        <XAxis dataKey="t" tickFormatter={timeTick} {...axisProps(t)} minTickGap={40} />
        <YAxis unit=" W" width={64} {...axisProps(t)} />
        <Tooltip
          {...tip}
          labelFormatter={(iso) => new Date(iso).toLocaleTimeString()}
          formatter={(v) => [`${Math.round(v)} W`, 'Power']}
        />
        <Area
          type="monotone" dataKey="power_W" name="Power"
          stroke={t.power} strokeWidth={2}
          fill={t.power} fillOpacity={0.14}
          dot={false} activeDot={{ r: 4 }} isAnimationActive={false}
          connectNulls
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function CurrentChart({ points }) {
  const t = useChartTheme();
  const tip = useTooltipStyles();
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={points} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={t.grid} vertical={false} />
        <XAxis dataKey="t" tickFormatter={timeTick} {...axisProps(t)} minTickGap={40} />
        <YAxis unit=" A" width={64} {...axisProps(t)} />
        <Tooltip
          {...tip}
          labelFormatter={(iso) => new Date(iso).toLocaleTimeString()}
          formatter={(v) => [`${v?.toFixed(2)} A`, 'Current']}
        />
        <Line
          type="monotone" dataKey="current_A" name="Current"
          stroke={t.current} strokeWidth={2}
          dot={false} activeDot={{ r: 4 }} isAnimationActive={false}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function DailyChart({ days }) {
  const t = useChartTheme();
  const tip = useTooltipStyles();
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={days} margin={{ top: 6, right: 8, left: 0, bottom: 0 }} barCategoryGap="35%">
        <CartesianGrid stroke={t.grid} vertical={false} />
        <XAxis
          dataKey="date" {...axisProps(t)}
          tickFormatter={(d) => d.slice(5)} // MM-DD
        />
        <YAxis unit=" kWh" width={70} {...axisProps(t)} />
        <Tooltip
          {...tip}
          formatter={(v, name, { payload }) =>
            [`${v} kWh · €${payload.cost_eur.toFixed(2)}`, 'Energy']}
        />
        <Bar
          dataKey="energy_kWh" name="Energy"
          fill={t.power} radius={[4, 4, 0, 0]} maxBarSize={26}
          isAnimationActive={false}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
