from pathlib import Path
import datetime as dt

import pandas as pd
import yfinance as yf

POS_FILE  = "posizioni_etf.csv"
HIST_FILE = "etf_returns_history.csv"

def resolve_ticker(ticker: str) -> str:
    """Ritorna il ticker effettivo da scaricare."""
    return ticker


def main():
    # 1) Carica posizioni
    pos = pd.read_csv(POS_FILE)
    pos["Quantita"]     = pos["Quantita"].astype(float)
    pos["Prezzo_carico"] = pos["Prezzo_carico"].astype(float)

    # Mappa ticker originale → ticker effettivo
    ticker_map = {
        row["Simbolo_Yahoo"]: resolve_ticker(row["Simbolo_Yahoo"])
        for _, row in pos.iterrows()
    }
    effective_tickers = list(set(ticker_map.values()))

    # 2) Scarica prezzi
    data = yf.download(
        effective_tickers,
        period="10d",
        interval="1d",
        auto_adjust=True,
        progress=False,
    )

    if isinstance(data.columns, pd.MultiIndex):
        prices = data["Close"]
    else:
        # Singolo ticker — yfinance non crea MultiIndex
        prices = data[["Close"]] if "Close" in data.columns else data
        prices.columns = [effective_tickers[0]]

    prices = prices.dropna(how="all").ffill()

    if prices.empty:
        print("Nessun prezzo disponibile da Yahoo.")
        return

    last_row  = prices.iloc[-1]
    last_date = last_row.name
    if isinstance(last_date, dt.datetime):
        last_date = last_date.date()

    # Prezzo per ticker effettivo
    eff_to_price = {
        t: float(last_row[t])
        for t in prices.columns
        if t in last_row.index and pd.notna(last_row[t])
    }

    # 3) Costruisce righe giornaliere
    rows = []
    for _, r in pos.iterrows():
        nome           = r["Nome"]
        ticker_orig    = r["Simbolo_Yahoo"]
        ticker_eff     = ticker_map[ticker_orig]
        prezzo_carico  = r["Prezzo_carico"]

        if ticker_eff not in eff_to_price:
            print(f"  ⚠ Nessun prezzo per {nome} ({ticker_orig} → {ticker_eff})")
            continue

        prezzo_oggi = eff_to_price[ticker_eff]
        rendimento  = (prezzo_oggi / prezzo_carico) - 1.0
        valore_att  = r["Quantita"] * prezzo_oggi
        valore_car  = r["Quantita"] * prezzo_carico
        pl_eur      = valore_att - valore_car

        rows.append({
            "data":                  last_date.isoformat(),
            "nome":                  nome,
            "ticker":                ticker_orig,
            "ticker_effettivo":      ticker_eff,
            "quantita":              r["Quantita"],
            "prezzo_carico":         prezzo_carico,
            "prezzo_oggi":           round(prezzo_oggi, 4),
            "valore_carico_eur":     round(valore_car, 2),
            "valore_attuale_eur":    round(valore_att, 2),
            "pl_eur":                round(pl_eur, 2),
            "rendimento_da_carico":  round(rendimento, 6),
            "rendimento_da_carico_%": round(rendimento * 100, 2),
        })

    if not rows:
        print("Nessuna riga da salvare.")
        return

    today_df = pd.DataFrame(rows)

    # Totale portafoglio
    tot_valore  = today_df["valore_attuale_eur"].sum()
    tot_carico  = today_df["valore_carico_eur"].sum()
    tot_pl      = today_df["pl_eur"].sum()
    tot_rend    = (tot_valore / tot_carico - 1) * 100

    print(f"\n{'─'*60}")
    print(f"  Data:              {last_date}")
    print(f"  Valore portafoglio: €{tot_valore:,.2f}")
    print(f"  Costo carico:       €{tot_carico:,.2f}")
    print(f"  P/L totale:         €{tot_pl:+,.2f}  ({tot_rend:+.2f}%)")
    print(f"{'─'*60}")
    print(today_df[["nome","prezzo_oggi","valore_attuale_eur",
                    "pl_eur","rendimento_da_carico_%"]].to_string(index=False))

    # 4) Append storico
    hist_path = Path(HIST_FILE)
    if hist_path.exists():
        hist = pd.read_csv(hist_path)
        hist = hist[hist["data"] != last_date.isoformat()]
        hist = pd.concat([hist, today_df], ignore_index=True)
    else:
        hist = today_df

    hist.to_csv(HIST_FILE, index=False)
    print(f"\n  ✓ Salvato {HIST_FILE} ({len(hist)} righe totali)")


if __name__ == "__main__":
    main()
