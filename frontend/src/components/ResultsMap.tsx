"use client";

import { useMemo, useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Building, Phone, Globe, ExternalLink } from "lucide-react";

interface Props {
  data: Record<string, any>[];
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

export default function ResultsMap({ data }: Props) {
  const geoData = useMemo(
    () => data.filter((r) => r.latitude != null && r.longitude != null),
    [data],
  );

  const positions = useMemo<[number, number][]>(
    () => geoData.map((r) => [r.latitude, r.longitude]),
    [geoData],
  );

  const defaultCenter: [number, number] = [46.603354, 1.888334]; // centre France

  if (geoData.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
        <div className="w-12 h-12 rounded-xl bg-white/[0.04] flex items-center justify-center mb-3">
          <Building size={20} className="text-gray-600" />
        </div>
        <p className="text-sm text-gray-500">
          Aucune entreprise avec coordonnées géographiques
        </p>
        <p className="text-xs text-gray-600 mt-1">
          Les adresses n&apos;ont pas pu être géolocalisées
        </p>
      </div>
    );
  }

  return (
    <div className="relative w-full h-[420px] sm:h-[480px] rounded-lg overflow-hidden">
      <MapContainer
        center={defaultCenter}
        zoom={6}
        className="w-full h-full"
        zoomControl={true}
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        <FitBounds positions={positions} />
        {geoData.map((row, i) => (
          <Marker key={i} position={[row.latitude, row.longitude]} icon={markerIcon}>
            <Popup>
              <div className="min-w-[200px] max-w-[280px]">
                <p className="font-semibold text-sm text-gray-900 leading-tight">
                  {row.nom || "—"}
                </p>
                {(row.adresse || row.ville) && (
                  <p className="text-xs text-gray-500 mt-1">
                    {[row.adresse, row.code_postal, row.ville].filter(Boolean).join(", ")}
                  </p>
                )}
                {row.libelle_activite && (
                  <p className="text-xs text-gray-600 mt-1 italic">{row.libelle_activite}</p>
                )}
                <div className="flex items-center gap-3 mt-2 pt-2 border-t border-gray-100">
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
      <div className="absolute bottom-3 left-3 z-[1000] bg-surface-2/90 backdrop-blur-sm border border-white/[0.08] rounded-lg px-2.5 py-1.5">
        <p className="text-[11px] text-gray-400">
          <span className="text-white font-medium tabular-nums">{geoData.length}</span>
          {" "}entreprise{geoData.length > 1 ? "s" : ""} sur la carte
          {geoData.length < data.length && (
            <span className="text-gray-600">
              {" "}/ {data.length} total
            </span>
          )}
        </p>
      </div>
    </div>
  );
}
