import { X } from "lucide-react";
import type { Order, TimelineEvent } from "../types";

type TimelineDrawerProps = {
  order: Order;
  events: TimelineEvent[];
  onClose: () => void;
};

export function TimelineDrawer({ order, events, onClose }: TimelineDrawerProps) {
  return (
    <aside className="drawer">
      <button className="icon-button" onClick={onClose} aria-label="Close timeline"><X size={18} /></button>
      <h2>{order.id} timeline</h2>
      <p>{order.priority_tier} {order.vertical} to {order.destination}</p>
      <div className="timeline">
        {events.map((event) => (
          <article key={event.id}>
            <span>T+{event.clock}m</span>
            <strong>{event.type.replace(/_/g, " ").toLowerCase()}</strong>
            <small>{event.actor} | {JSON.stringify(event.payload)}</small>
          </article>
        ))}
      </div>
    </aside>
  );
}
