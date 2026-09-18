from pathlib import Path
import datetime as dt

import pandas as pd
import yfinance as yf

POS_FILE  = "posizioni_etf.csv"
HIST_FILE = "etf_returns_history.csv"


def main():
    # 1) Carica posizioni
    pos = pd.read_csv(POS_FILE)
    pos["Quantita"]      = pos["Quantita"].astype(float)
    pos["Prezzo_carico"] = pos["Prezzo_carico"].astype(float)

    tickers = pos["Simbolo_Yahoo"].tolist()

    # 2) Scarica prezzi ultimi 10 giorni
    data = yf.download(
        tickers,
        period="10d",
        interval="1d",
        auto_adjust=True,
        progress=False,
    )

    if isinstance(data.columns, pd.MultiIndex):
        prices = data["Close"]
    else:
        prices = data[["Close"]]
        prices.columns = [tickers[0]]

    prices = prices.dropna(how="all").ffill()

    if prices.empty:
        print("Nessun prezzo disponibile da Yahoo.")
        return

    last_row  = prices.iloc[-1]
    last_date = last_row.name
    if isinstance(last_date, dt.datetime):
        last_date = last_date.date()

    # 3) Carica prezzi giorno precedente per sanity check outlier
    hist_path = Path(HIST_FILE)
    prev_prices = {}
    if hist_path.exists():
        hist = pd.read_csv(hist_path)
        if not hist.empty:
            last_hist_date = hist["data"].max()
            prev = hist[hist["data"] == last_hist_date].set_index("ticker")
            prev_prices = prev["prezzo_oggi"].to_dict()

    # 4) Costruisce righe giornaliere
    rows = []
    for _, r in pos.iterrows():
        nome          = r["Nome"]
        ticker        = r["Simbolo_Yahoo"]
        prezzo_carico = r["Prezzo_carico"]

        if ticker not in last_row.index or pd.isna(last_row[ticker]):
            print(f"  ⚠ Nessun prezzo per {nome} ({ticker})")
            continue

        prezzo_oggi = float(last_row[ticker])

        # Sanity check: salta prezzi anomali (>10x o <0.1x rispetto a ieri)
        if ticker in prev_prices and prev_prices[ticker] > 0:
            ratio = prezzo_oggi / prev_prices[ticker]
            if ratio > 10 or ratio < 0.1:
                print(f"  ⚠ Prezzo anomalo {nome} ({ticker}): {prezzo_oggi:.4f} vs ieri {prev_prices[ticker]:.4f} — saltato")
                continue

        quantita   = r["Quantita"]
        val_att    = quantita * prezzo_oggi
        val_car    = quantita * prezzo_carico
        pl_eur     = val_att - val_car
        rendimento = (prezzo_oggi / prezzo_carico) - 1.0

        rows.append({
            "data":                   last_date.isoformat(),
            "nome":                   nome,
            "ticker":                 ticker,
            "ticker_effettivo":       ticker,
            "quantita":               quantita,
            "prezzo_carico":          prezzo_carico,
            "prezzo_oggi":            round(prezzo_oggi, 4),
            "valore_carico_eur":      round(val_car, 2),
            "valore_attuale_eur":     round(val_att, 2),
            "pl_eur":                 round(pl_eur, 2),
            "rendimento_da_carico":   round(rendimento, 6),
            "rendimento_da_carico_%": round(rendimento * 100, 2),
        })

    if not rows:
        print("Nessuna riga da salvare.")
        return

    today_df = pd.DataFrame(rows)

    # Riepilogo portafoglio
    tot_att  = today_df["valore_attuale_eur"].sum()
    tot_car  = today_df["valore_carico_eur"].sum()
    tot_pl   = today_df["pl_eur"].sum()
    tot_rend = (tot_att / tot_car - 1) * 100

    print(f"\n{'─'*60}")
    print(f"  Data:               {last_date}")
    print(f"  Valore portafoglio: €{tot_att:,.2f}")
    print(f"  Costo carico:       €{tot_car:,.2f}")
    print(f"  P/L totale:         €{tot_pl:+,.2f}  ({tot_rend:+.2f}%)")
    print(f"{'─'*60}")
    print(today_df[["nome", "prezzo_oggi", "valore_attuale_eur",
                     "pl_eur", "rendimento_da_carico_%"]].to_string(index=False))

    # 5) Append allo storico (sovrascrive eventuale riga con stessa data)
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
