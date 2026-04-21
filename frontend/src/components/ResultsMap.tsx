"use client";

import { useMemo, useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Building, Phone, Globe, ExternalLink } from "lucide-react";
import { useTheme } from "next-themes";

interface Props {
  data: Record<string, any>[];
  /** Par défaut h-[420px] sm:h-[480px] ; passer h-full quand le parent impose la hauteur. */
  className?: string;
}

const markerIcon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

function FitBounds({ positions }: { positions: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (positions.length === 0) return;
    if (positions.length === 1) {
      map.setView(positions[0], 13);
      return;
    }
    const bounds = L.latLngBounds(positions.map(([lat, lng]) => [lat, lng]));
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
  }, [map, positions]);
  return null;
}

const DEFAULT_MAP_BOX = "h-[420px] sm:h-[480px]";

function ThemedTileLayer() {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const dark = !mounted || resolvedTheme !== "light";
  return (
    <TileLayer
      attribution={
        dark
          ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
          : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      }
      url={
        dark
          ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      }
    />
  );
}

export default function ResultsMap({ data, className }: Props) {
  const geoData = useMemo(
    () => data.filter((r) => r.latitude != null && r.longitude != null),
    [data],
  );

  const positions = useMemo<[number, number][]>(
    () => geoData.map((r) => [r.latitude, r.longitude]),
    [geoData],
  );

  const defaultCenter: [number, number] = [46.603354, 1.888334]; // centre France

  const boxClass = className?.trim() ? className : DEFAULT_MAP_BOX;

  if (geoData.length === 0) {
    return (
      <div
        className={`flex min-h-0 w-full flex-col items-center justify-center rounded-lg border border-border bg-muted/30 px-4 text-center ${boxClass}`}
      >
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-muted">
          <Building size={20} className="text-muted-foreground" />
        </div>
        <p className="text-sm text-muted-foreground">
          Aucune entreprise avec coordonnées géographiques
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          Les adresses n&apos;ont pas pu être géolocalisées
        </p>
      </div>
    );
  }

  return (
    <div className={`relative w-full rounded-lg overflow-hidden ${boxClass}`}>
      <MapContainer
        center={defaultCenter}
        zoom={6}
        className="w-full h-full"
        zoomControl={true}
        scrollWheelZoom={true}
      >
        <ThemedTileLayer />
        <FitBounds positions={positions} />
        {geoData.map((row, i) => (
          <Marker key={i} position={[row.latitude, row.longitude]} icon={markerIcon}>
            <Popup>
              <div className="min-w-[200px] max-w-[280px]">
                <p className="text-sm font-semibold leading-tight text-foreground">
                  {row.nom || "—"}
                </p>
                {(row.adresse || row.ville) && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {[row.adresse, row.code_postal, row.ville].filter(Boolean).join(", ")}
                  </p>
                )}
                {row.libelle_activite && (
                  <p className="text-xs text-muted-foreground mt-1 italic">{row.libelle_activite}</p>
                )}
                <div className="mt-2 flex items-center gap-3 border-t border-border pt-2">
                  {row.telephone && (
                    <a
                      href={`tel:${row.telephone}`}
                      className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700"
                    >
                      <Phone size={10} />
                      {row.telephone}
                    </a>
                  )}
                  {row.site_web && (
                    <a
                      href={String(row.site_web).startsWith("http") ? row.site_web : `https://${row.site_web}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700"
                    >
                      <Globe size={10} />
                      Site
                    </a>
                  )}
                  {row.lien_annuaire && (
                    <a
                      href={row.lien_annuaire}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700"
                    >
                      <ExternalLink size={10} />
                      Fiche
                    </a>
                  )}
                </div>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
      <div className="absolute bottom-3 left-3 z-[1000] rounded-lg border border-border bg-background/90 px-2.5 py-1.5 backdrop-blur-sm">
        <p className="text-[11px] text-muted-foreground">
          <span className="font-mono font-medium tabular-nums text-foreground">{geoData.length}</span>
          {" "}entreprise{geoData.length > 1 ? "s" : ""} sur la carte
          {geoData.length < data.length && (
            <span className="text-muted-foreground">
              {" "}/ {data.length} total
            </span>
          )}
        </p>
      </div>
    </div>
  );
}
