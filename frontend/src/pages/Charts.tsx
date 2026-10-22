import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import type { ChartDay } from "../types";

const MIX_COLORS = ["#1f7a4d", "#c8bfb2", "#9d341f", "#315f8c", "#3d6b4f", "#7a3e12", "#8a6a12", "#6d5a1e", "#5c4d86", "#4a1f2c"];

export function Charts() {
  const [days, setDays] = useState<ChartDay[]>([]);
  const [mix, setMix] = useState<{ status: string; agent_days: number }[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.charts()
      .then((body) => {
        setDays(body.days.map((day) => ({ ...day, label: Number(day.date.slice(8)) })));
        setMix(body.mix);
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!days.length) return <p className="muted">Loading charts...</p>;

  return (
    <section className="chart-grid">
      <article className="card">
        <h2>Forecast requirement vs present FTE</h2>
        <div className="chart-box">
          <ResponsiveContainer>
            <LineChart data={days}>
              <CartesianGrid stroke="#eee6da" />
              <XAxis dataKey="label" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="required_agents" name="Required" stroke="#9d341f" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="present_fte" name="Present FTE" stroke="#0d5c56" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </article>
      <article className="card">
        <h2>Forecast volume trend</h2>
        <div className="chart-box">
          <ResponsiveContainer>
            <LineChart data={days}>
              <CartesianGrid stroke="#eee6da" />
              <XAxis dataKey="label" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="forecast_volume" name="Volume" stroke="#315f8c" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </article>
      <article className="card">
        <h2>Attendance and leave mix</h2>
        <div className="chart-box">
          <ResponsiveContainer>
            <PieChart>
              <Pie data={mix} dataKey="agent_days" nameKey="status" outerRadius={90}>
                {mix.map((entry, index) => <Cell key={entry.status} fill={MIX_COLORS[index % MIX_COLORS.length]} />)}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </article>
      <article className="card">
        <h2>Capacity surplus / shortfall</h2>
        <div className="chart-box">
          <ResponsiveContainer>
            <BarChart data={days}>
              <CartesianGrid stroke="#eee6da" />
              <XAxis dataKey="label" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="surplus" name="Surplus">
                {days.map((day) => <Cell key={day.date} fill={day.surplus < 0 ? "#9d341f" : "#0f7a45"} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </article>
    </section>
  );
}
