import { useNavigate } from "react-router";
import { FleetMap } from "@/components/map/FleetMap";
import { Loading } from "@/components/states/Loading";
import { ErrorState } from "@/components/states/ErrorState";
import { useDevices, useFences, useHealth } from "@/api/hooks";
import { useT } from "@/lib/i18n";

const legend = [
  { key: "map.legend.inside", color: "#346538" },
  { key: "map.legend.outside", color: "#956400" },
  { key: "map.legend.unknown", color: "#5E635C" },
] as const;

export function MapPage() {
  const t = useT();
  const navigate = useNavigate();
  const health = useHealth();
  const fences = useFences();
  const devices = useDevices();
  const error = health.error ?? fences.error ?? devices.error;
  return (
    <div className="flex h-[calc(100dvh-8rem)] flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{t("map.title")}</h1>
        <ul className="flex gap-4 text-sm text-fg-2">
          {legend.map((l) => (
            <li key={l.key} className="flex items-center gap-2">
              <span className="inline-block h-3 w-3 rounded-full" style={{ background: l.color }} aria-hidden />
              {t(l.key)}
            </li>
          ))}
        </ul>
      </div>
      {error && <ErrorState error={error} />}
      {(health.isPending || fences.isPending || devices.isPending) && <Loading rows={6} />}
      {health.data && (!health.data.map.enabled || !health.data.map.tiles_url) && <p className="text-sm text-muted">{t("map.disabled")}</p>}
      {health.data?.map.enabled && health.data.map.tiles_url && fences.data && devices.data && (
        <div className="min-h-0 flex-1">
          <FleetMap fences={fences.data.items} devices={devices.data.items} tilesUrl={health.data.map.tiles_url} onDeviceClick={(id) => navigate(`/devices/${id}`)} />
        </div>
      )}
    </div>
  );
}
