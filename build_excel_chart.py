import pandas as pd
from pathlib import Path

INPUT_CSV = "etf_returns_history.csv"
POSITIONS_CSV = "posizioni_etf.csv"
OUTPUT_XLSX = "grafico_portafoglio.xlsx"

# ETF da escludere dal grafico (volatilità troppo alta o dati non affidabili)
EXCLUDE_FROM_CHART = {"Bitcoin_ETP"}

def main():
    csv_path = Path(INPUT_CSV)
    pos_path = Path(POSITIONS_CSV)

    if not csv_path.exists():
        raise FileNotFoundError(f"File non trovato: {INPUT_CSV}")
    if not pos_path.exists():
        raise FileNotFoundError(f"File non trovato: {POSITIONS_CSV}")

    # Carica dati storici
    df = pd.read_csv(csv_path)
    pos = pd.read_csv(pos_path)

    df["data"] = pd.to_datetime(df["data"])
    df = df.sort_values(["data", "nome"]).copy()

    # Unisci quantità dal file posizioni
    pos = pos[["Nome", "Quantita"]].copy()
    df = df.merge(pos, left_on="nome", right_on="Nome", how="left")

    if df["Quantita"].isna().any():
        missing = df.loc[df["Quantita"].isna(), "nome"].unique().tolist()
        raise ValueError(f"Mancano le quantità per questi ETF: {missing}")

    # Calcolo rendimento totale del portafoglio pesato
    df["valore_iniziale"] = df["Quantita"] * df["prezzo_carico"]
    df["valore_corrente"] = df["Quantita"] * df["prezzo_oggi"]

    grouped = df.groupby("data", as_index=True)[["valore_iniziale", "valore_corrente"]].sum()
    grouped["Portafoglio_totale"] = grouped["valore_corrente"] / grouped["valore_iniziale"] - 1.0

    # Pivot ETF singoli
    pivot = df.pivot(index="data", columns="nome", values="rendimento_da_carico").sort_index()

    # Tabella finale per grafico
    chart_df = pivot.copy()
    chart_df["Portafoglio_totale"] = grouped["Portafoglio_totale"]
    chart_df = chart_df.sort_index()
    chart_df.index.name = "Data"

    # Scrittura Excel + grafico
    with pd.ExcelWriter(OUTPUT_XLSX, engine="xlsxwriter", datetime_format="yyyy-mm-dd") as writer:
        # Foglio raw
        df.to_excel(writer, sheet_name="storico_raw", index=False)

        # Foglio dati grafico
        chart_df_reset = chart_df.reset_index()
        chart_df_reset.to_excel(writer, sheet_name="grafico_dati", index=False)

        workbook = writer.book
        ws = writer.sheets["grafico_dati"]

        percent_fmt = workbook.add_format({"num_format": "0.00%"})
        date_fmt = workbook.add_format({"num_format": "yyyy-mm-dd"})

        # Formattazione colonne
        ws.set_column(0, 0, 14, date_fmt)   # Data
        ws.set_column(1, len(chart_df_reset.columns) - 1, 16, percent_fmt)

        # Crea grafico linee
        chart = workbook.add_chart({"type": "line"})

        max_row = len(chart_df_reset)
        max_col = len(chart_df_reset.columns)

        # Aggiungi serie ETF singoli
        for col_idx in range(1, max_col):
            series_name = chart_df_reset.columns[col_idx]

            # Portafoglio totale in nero e più spesso
            if series_name == "Portafoglio_totale":
                chart.add_series({
                    "name":       ["grafico_dati", 0, col_idx],
                    "categories": ["grafico_dati", 1, 0, max_row, 0],
                    "values":     ["grafico_dati", 1, col_idx, max_row, col_idx],
                    "line":       {"color": "black", "width": 2.75},
                })
            else:
                chart.add_series({
                    "name":       ["grafico_dati", 0, col_idx],
                    "categories": ["grafico_dati", 1, 0, max_row, 0],
                    "values":     ["grafico_dati", 1, col_idx, max_row, col_idx],
                    "line":       {"width": 1.25},
                })

        chart.set_title({"name": "Rendimento portafoglio vs singoli ETF"})
        chart.set_x_axis({"name": "Tempo", "date_axis": True})
        chart.set_y_axis({"name": "Rendimento", "num_format": "0%"})
        chart.set_legend({"position": "bottom"})
        chart.set_size({"width": 1200, "height": 650})

        # Nuovo foglio solo per il grafico
        chart_sheet = workbook.add_worksheet("grafico")
        chart_sheet.insert_chart("B2", chart)

    print(f"Creato file Excel: {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()
