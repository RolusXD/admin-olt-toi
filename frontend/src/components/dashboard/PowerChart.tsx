const points = [-21.4, -22.1, -23.6, -24.3, -25.8, -23.9, -22.8, -26.2, -24.7, -23.1];

export function PowerChart() {
  return (
    <div className="h-64 rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-950">Tendencia RX promedio</h2>
        <span className="text-xs text-muted">Ultimas 10 muestras</span>
      </div>
      <div className="flex h-44 items-end gap-2">
        {points.map((value, index) => {
          const height = Math.max(28, 150 - Math.abs(value + 20) * 16);
          const tone = value < -27 ? "bg-danger" : value <= -24 ? "bg-warning" : "bg-primary";
          return (
            <div key={`${value}-${index}`} className="flex flex-1 flex-col items-center gap-2">
              <div className={`w-full rounded-t-sm ${tone}`} style={{ height }} title={`${value} dBm`} />
              <span className="text-[10px] text-muted">{value}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
