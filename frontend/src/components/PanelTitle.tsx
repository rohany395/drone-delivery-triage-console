import type { ReactNode } from "react";

type PanelTitleProps = {
  icon: ReactNode;
  title: string;
  detail: string;
};

export function PanelTitle({ icon, title, detail }: PanelTitleProps) {
  return (
    <div className="panel-title">
      <span>{icon}</span>
      <h2>{title}</h2>
      <small>{detail}</small>
    </div>
  );
}
