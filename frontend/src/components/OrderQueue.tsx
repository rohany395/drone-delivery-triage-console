import { Stethoscope } from "lucide-react";
import type { AppState, Order } from "../types";
import { classNames, slaMinutes } from "../utils";
import { PanelTitle } from "./PanelTitle";

type OrderQueueProps = {
  state: AppState;
  gaugePct: number;
  onSelectOrder: (order: Order) => void;
};

export function OrderQueue({ state, gaugePct, onSelectOrder }: OrderQueueProps) {
  const pendingOrders = state.orders.filter((order) => ["pending", "assigned", "in_flight"].includes(order.state));

  return (
    <section className="panel queue-panel">
      <PanelTitle icon={<Stethoscope />} title="Order Queue" detail={`${state.metrics.backlog} pending, ${state.metrics.throughput_per_hour}/hr capacity`} />
      <div className="capacity-bar">
        <div style={{ width: `${Math.min(100, gaugePct)}%` }} />
      </div>
      <div className="orders">
        {pendingOrders.map((order, index) => (
          <button key={order.id} className={classNames("order-row", order.priority_tier.toLowerCase())} onClick={() => onSelectOrder(order)}>
            <span className="rank">{index + 1}</span>
            <span className="tier">{order.priority_tier}</span>
            <span>
              <strong>{order.id}</strong>
              <small>{order.vertical} to {order.destination}</small>
            </span>
            <span className={classNames("state-pill", order.state)}>{order.state.replace("_", " ")}</span>
            <span className={classNames("sla", slaMinutes(order, state.clock) <= 15 && "hot")}>{slaMinutes(order, state.clock)}m SLA</span>
            <span>{order.assigned_aircraft_id ?? "unassigned"}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
