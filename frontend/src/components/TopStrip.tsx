import { Clock3, Gauge, Plane, ShieldAlert } from "lucide-react";
import type { AppState } from "../types";
import { classNames } from "../utils";
import { Metric } from "./Metric";

type TopStripProps = {
  state: AppState;
  gaugePct: number;
};

export function TopStrip({ state, gaugePct }: TopStripProps) {
  return (
    <header className="top-strip">
      <div>
        <p className="eyebrow">Zipline-style single nest demo</p>
        <h1>{state.nest.name}</h1>
      </div>
      <Metric icon={<Clock3 />} label="Sim clock" value={`T+${state.clock}m`} />
      <Metric icon={<Gauge />} label="Capacity" value={`${gaugePct}%`} tone={gaugePct > 115 ? "danger" : gaugePct > 90 ? "warn" : "ok"} />
      <Metric icon={<Plane />} label="Fleet" value={`${state.metrics.ready_aircraft}/${state.fleet.length} ready`} />
      <Metric icon={<ShieldAlert />} label="SLA risk" value={`${state.metrics.sla_risk}`} tone={state.metrics.sla_risk ? "warn" : "ok"} />
      <div className={classNames("weather", state.nest.status === "degraded" && "degraded")}>
        <span>{state.nest.weather_state.replace("_", " ")}</span>
        <strong>{state.nest.status}</strong>
      </div>
    </header>
  );
}
