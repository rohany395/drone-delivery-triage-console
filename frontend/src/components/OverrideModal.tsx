import { UserPen, X } from "lucide-react";
import type { Order } from "../types";

type OverrideModalProps = {
  order: Order;
  operator: string;
  reason: string;
  targetAction: string;
  onOperatorChange: (value: string) => void;
  onReasonChange: (value: string) => void;
  onTargetActionChange: (value: string) => void;
  onSubmit: () => void;
  onClose: () => void;
};

export function OverrideModal({
  order,
  operator,
  reason,
  targetAction,
  onOperatorChange,
  onReasonChange,
  onTargetActionChange,
  onSubmit,
  onClose
}: OverrideModalProps) {
  return (
    <div className="modal-backdrop">
      <section className="modal">
        <button className="icon-button" onClick={onClose} aria-label="Close override"><X size={18} /></button>
        <h2>Override {order.id}</h2>
        <p>{order.priority_tier} {order.vertical}. P0 deferrals require a clear logged reason.</p>
        <label>
          Operator
          <input value={operator} onChange={(event) => onOperatorChange(event.target.value)} />
        </label>
        <label>
          Target action
          <select value={targetAction} onChange={(event) => onTargetActionChange(event.target.value)}>
            <option value="ground_fallback">Ground fallback</option>
            <option value="deferred">Deferred</option>
            <option value="pending">Return to pending</option>
            <option value="failed">Failed</option>
          </select>
        </label>
        <label>
          Reason
          <textarea value={reason} onChange={(event) => onReasonChange(event.target.value)} />
        </label>
        <button className="primary-action" disabled={!operator.trim() || !reason.trim()} onClick={onSubmit}>
          <UserPen size={16} /> Log override
        </button>
      </section>
    </div>
  );
}
