import type { ReactNode } from "react";
import { classNames } from "../utils";

type MetricProps = {
  icon: ReactNode;
  label: string;
  value: string;
  tone?: "ok" | "warn" | "danger";
};

export function Metric({ icon, label, value, tone }: MetricProps) {
  return (
    <div className={classNames("metric", tone)}>
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
