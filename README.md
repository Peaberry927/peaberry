# Peaberry

Peaberry is a small FastAPI/SQLite foundation for quant-oriented valuation
snapshots.

## Data-source order

1. Current price
   - Korean equities: Naver Finance
   - US equities: Yahoo Finance fallback
2. KOSPI/KOSDAQ index values
   - Naver Finance index pages
3. OpenDART annual financials
   - Korean annual statements use `fnlttSinglAcntAll`
   - Set `OPENDART_API_KEY` and provide `corp_code`
4. Naver valuation fields
   - PER, PBR, EPS, BPS for Korean equities
5. Yahoo fallback
   - Explicitly allowed only for US stocks
6. Stale fallback cleanup
   - Yahoo fallback rows for non-US securities are removed from SQLite

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000`.

The snapshot response includes a `display` section for UI-safe presentation:

- Korean annual financial amounts are shown in `억원` from OpenDART KRW raw values.
- US annual financial amounts are shown in `USD mn` from Yahoo USD raw values.
- EPS/BPS use per-share currency units, PER/PBR use `배`, and ROE uses `%`.
- Missing display cells include fill metadata, and the web UI can save manual blank fills locally.

## Test

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```
