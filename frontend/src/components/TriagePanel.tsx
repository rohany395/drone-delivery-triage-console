import { CheckCircle2, ShieldAlert, UserPen } from "lucide-react";
import type { Order, PlanItem, Triage } from "../types";
import { classNames } from "../utils";
import { PanelTitle } from "./PanelTitle";
import { Stat } from "./Stat";

type TriagePanelProps = {
  triage: Triage;
  ordersById: Map<string, Order>;
  onApplyPlan: () => void;
  onOverride: (order: Order) => void;
};

export function TriagePanel({ triage, ordersById, onApplyPlan, onOverride }: TriagePanelProps) {
  return (
    <section className="panel triage-panel">
      <PanelTitle icon={<ShieldAlert />} title="Triage" detail={triage.capacity_tight ? "Capacity constrained" : "Monitoring"} />
      <div className="triage-summary">
        <Stat label="Medical protected" value={triage.summary.medical_orders_protected} />
        <Stat label="Retail deferred" value={triage.summary.retail_deferred} />
        <Stat label="FIFO P0 misses" value={triage.fifo_baseline.deferred_p0_count} />
      </div>
      <p className="risk-note">{triage.fifo_baseline.risk}</p>
      <div className="triage-columns">
        <PlanColumn title="Protect now" items={triage.plan.protect_now} byId={ordersById} tone="protect" onOverride={onOverride} />
        <PlanColumn title="Defer" items={triage.plan.defer} byId={ordersById} tone="defer" onOverride={onOverride} />
        <PlanColumn title="Ground fallback" items={triage.plan.ground_fallback} byId={ordersById} tone="fallback" onOverride={onOverride} />
      </div>
      <button className="primary-action" onClick={onApplyPlan}><CheckCircle2 size={16} /> Apply plan</button>
    </section>
  );
}

function PlanColumn({
  title,
  items,
  byId,
  tone,
  onOverride
}: {
  title: string;
  items: PlanItem[];
  byId: Map<string, Order>;
  tone: string;
  onOverride: (order: Order) => void;
}) {
  return (
    <div className={classNames("plan-column", tone)}>
      <h3>{title}</h3>
      {items.slice(0, 7).map((item) => {
        const order = byId.get(item.order_id);
        return (
          <article key={item.order_id}>
            <span>{order?.priority_tier ?? "?"}</span>
            <strong>{item.order_id}</strong>
            <p>{item.rationale}</p>
            {order && <button onClick={() => onOverride(order)}><UserPen size={14} /> Override</button>}
          </article>
        );
      })}
    </div>
  );
}
