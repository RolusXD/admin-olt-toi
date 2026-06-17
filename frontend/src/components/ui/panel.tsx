import { HTMLAttributes } from "react";
import clsx from "clsx";

export function Panel({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx("rounded-lg border border-slate-200 bg-white shadow-panel", className)} {...props} />;
}
