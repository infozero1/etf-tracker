from pathlib import Path
import datetime as dt

import pandas as pd
import yfinance as yf

POS_FILE = "posizioni_etf.csv"
HIST_FILE = "etf_returns_history.csv"


def main():
    # 1) Carica posizioni
    pos = pd.read_csv(POS_FILE)
    pos["Quantita"] = pos["Quantita"].astype(float)
    pos["Prezzo_carico"] = pos["Prezzo_carico"].astype(float)

    names = pos["Nome"].tolist()
    tickers = pos["Simbolo_Yahoo"].tolist()

    # 2) Scarica ultimi prezzi di chiusura da Yahoo
    data = yf.download(
        tickers,
        period="5d",          # ultimi giorni, basta per avere l'ultimo close
        interval="1d",
        auto_adjust=True,
        progress=False,
    )

    if isinstance(data.columns, pd.MultiIndex):
        prices = data["Close"]
    else:
        prices = data

    prices = prices.dropna(how="all")
    if prices.empty:
        print("Nessun prezzo disponibile da Yahoo.")
        return

    # ultima riga disponibile (ultimo giorno di borsa)
    last_row = prices.iloc[-1]
    last_date = last_row.name
    if isinstance(last_date, dt.datetime):
        last_date = last_date.date()

    ticker_to_price = {
        t: float(last_row[t])
        for t in prices.columns
        if pd.notna(last_row[t])
    }

    # 3) Costruisce il dataframe giornaliero con rendimento da carico
    rows = []
    for _, r in pos.iterrows():
        nome = r["Nome"]
        ticker = r["Simbolo_Yahoo"]
        prezzo_carico = r["Prezzo_carico"]

        if ticker not in ticker_to_price:
            # nessun dato oggi per questo ticker
            continue

        prezzo_oggi = ticker_to_price[ticker]
        rendimento = (prezzo_oggi / prezzo_carico) - 1.0  # es. 0.25 = +25%

        rows.append(
            {
                "data": last_date.isoformat(),
                "nome": nome,
                "ticker": ticker,
                "prezzo_carico": prezzo_carico,
                "prezzo_oggi": prezzo_oggi,
                "rendimento_da_carico": rendimento,
                "rendimento_da_carico_%": round(rendimento * 100, 2),
            }
        )

    if not rows:
        print("Nessuna riga da salvare (nessun prezzo valido oggi).")
        return

    today_df = pd.DataFrame(rows)

    # 4) Append allo storico
    hist_path = Path(HIST_FILE)
    if hist_path.exists():
        hist = pd.read_csv(hist_path)
        # rimuovi eventuali righe già presenti per questa data
        hist = hist[hist["data"] != last_date.isoformat()]
        hist = pd.concat([hist, today_df], ignore_index=True)
    else:
        hist = today_df

    hist.to_csv(HIST_FILE, index=False)

    print(f"Aggiornato {HIST_FILE} per la data {last_date.isoformat()}")
    print(hist.tail(len(rows)))


if __name__ == "__main__":
    main()
