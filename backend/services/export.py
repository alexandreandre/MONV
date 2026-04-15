"""
Couche 4 — Sortie et livraison
Génère des fichiers Excel et CSV à partir des résultats de recherche.
"""

import pandas as pd
import uuid
from pathlib import Path
from datetime import datetime

from models.schemas import SearchResults, CompanyResult
from config import settings

COLUMN_LABELS = {
    "nom": "Raison sociale",
    "siren": "SIREN",
    "siret": "SIRET",
    "activite_principale": "Code NAF",
    "libelle_activite": "Activité",
    "adresse": "Adresse",
    "code_postal": "Code postal",
    "ville": "Ville",
    "region": "Région",
    "departement": "Département",
    "tranche_effectif": "Effectif (code)",
    "effectif_label": "Effectif",
    "date_creation": "Date création",
    "forme_juridique": "Forme juridique",
    "dirigeant_nom": "Nom dirigeant",
    "dirigeant_prenom": "Prénom dirigeant",
    "dirigeant_fonction": "Fonction dirigeant",
    "chiffre_affaires": "Chiffre d'affaires (€)",
    "resultat_net": "Résultat net (€)",
    "email": "Email",
    "telephone": "Téléphone",
    "site_web": "Site web",
    "lien_annuaire": "Fiche Annuaire",
    "google_maps_url": "Google Maps",
}


def _results_to_dataframe(results: SearchResults) -> pd.DataFrame:
    """Convert search results to a DataFrame with the right columns."""
    data = []
    for r in results.results:
        row = r.model_dump()
        data.append(row)

    df = pd.DataFrame(data)
    if df.empty:
        return df

    cols_to_keep = [c for c in results.columns if c in df.columns]
    if "lien_annuaire" in df.columns and "lien_annuaire" not in cols_to_keep:
        cols_to_keep.append("lien_annuaire")
    if "effectif_label" in df.columns and "effectif_label" not in cols_to_keep:
        cols_to_keep.append("effectif_label")

    df = df[cols_to_keep]
    df = df.rename(columns={c: COLUMN_LABELS.get(c, c) for c in df.columns})
    return df


def generate_excel(results: SearchResults, query_text: str = "") -> str:
    """Generate an Excel file and return its path."""
    df = _results_to_dataframe(results)
    filename = f"monv_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.xlsx"
    filepath = Path(settings.EXPORTS_DIR) / filename

    with pd.ExcelWriter(str(filepath), engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Résultats", index=False)

        ws = writer.sheets["Résultats"]

        from openpyxl.styles import Font, PatternFill, Alignment
        header_fill = PatternFill("solid", fgColor="0F172A")
        header_font = Font(bold=True, color="FFFFFF", size=10)
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", wrap_text=True)

        for col_idx, col in enumerate(df.columns, 1):
            max_len = max(len(str(col)), df[col].astype(str).str.len().max() if len(df) > 0 else 0)
            ws.column_dimensions[ws.cell(1, col_idx).column_letter].width = min(max_len + 4, 40)

        ws.freeze_panes = "A2"

        if query_text:
            info_ws = writer.book.create_sheet("Info")
            info_ws["A1"] = "Requête"
            info_ws["B1"] = query_text
            info_ws["A2"] = "Date d'export"
            info_ws["B2"] = datetime.now().strftime("%d/%m/%Y %H:%M")
            info_ws["A3"] = "Nombre de résultats"
            info_ws["B3"] = results.total
            info_ws["A4"] = "Généré par"
            info_ws["B4"] = "MONV — monv.fr"
            for cell in [info_ws["A1"], info_ws["A2"], info_ws["A3"], info_ws["A4"]]:
                cell.font = Font(bold=True)
            info_ws.column_dimensions["A"].width = 25
            info_ws.column_dimensions["B"].width = 60

    return str(filepath)


def generate_csv(results: SearchResults) -> str:
    """Generate a CSV file and return its path."""
    df = _results_to_dataframe(results)
    filename = f"monv_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.csv"
    filepath = Path(settings.EXPORTS_DIR) / filename
    df.to_csv(str(filepath), index=False, encoding="utf-8-sig")
    return str(filepath)
