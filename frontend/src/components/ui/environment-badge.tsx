import clsx from "clsx";

export function EnvironmentBadge({ environment }: { environment?: string | null }) {
  const isLab = environment === "lab";
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md px-2 py-1 text-xs font-medium",
        isLab ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800",
      )}
    >
      {isLab ? "Laboratorio" : "Produccion"}
    </span>
  );
}
