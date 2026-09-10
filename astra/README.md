# Retrieve and import ETF holdings

Use the existing script with `--import-db` to write directly to the project's
PostgreSQL `holdings` table instead of exporting holdings JSON.

## Prerequisites

- Run from a checkout containing both `astra` and `backend`, using the backend's
  Python environment/dependencies (SQLAlchemy and psycopg2 are already declared).
- Set `DATABASE_URL` in the process environment to the intended PostgreSQL database.
  The script does not automatically read a `.env` file or initialize the schema.
- Import the ETF metadata first: its ISIN must already exist in `etfs`.

From the repository root:

```shell
python astra/smi_reconstruction.py IE00B4L5Y983 --provider ishares --import-db
python astra/smi_reconstruction.py IE00B5BMR087 --provider ishares --import-db
python astra/smi_reconstruction.py IE00BD4TXV59 --provider ubs --holdings-file ubs.csv --as-of 2026-09-08 --import-db
```

iShares discovers its full holdings via ISIN; `--product-url` supplies an explicit
share-class page when discovery fails. UBS automatic discovery is still pending:
use a full CSV/JSON portfolio export or `--holdings-url` with a public UBS download.
Dates embedded in exports are used automatically; `--as-of` fills a missing date.

Existing parser options still apply: `--weight-unit fraction`, `--decimal-comma`,
`--equities-only` when the export omits asset class, and `--isin-map`. Missing ISINs
fail by default; `--allow-missing-isins` explicitly permits database nulls.
Top-ten factsheets are not full portfolios; `--allow-partial` must be explicit
for equity coverage below 80%. Cash and derivatives are excluded.

## Database behavior

- Stores the provider's `reported_weight × 100` as percent of fund NAV. It does
  **not** store the equity-normalized `weight` or assume equities total 100%.
- Replaces only the requested ETF's holdings on the source valuation date.
  Repeating an import is safe: it replaces that snapshot rather than appending duplicates.
- Uses a transaction and locks the ETF during replacement. Insert failures roll
  back the deletion. Invalid baskets are rejected before any delete.
- Leaves other dates, ETF metadata, performance and allocations unchanged.
  This is a holdings-only import, not an allocation refresh. The script does not
  supply country/sector classifications; new rows leave those fields null.
- The database requires security ISINs to be unique per ETF/date. Multiple listings
  of the same ISIN are combined, even if names differ. Different ISINs may share a
  name. Unresolved ISINs remain separate null-valued rows rather than being guessed.
- Rejects reconstruction/demo mode for database imports.

Without `--import-db`, existing JSON export behavior is unchanged. Diagnostic
JSON files are still written; `--stdout` still optionally prints the basket.
The backend migrates existing name-based uniqueness to ISIN-based uniqueness on
startup, combining existing same-ISIN rows by summing weights. Redeploy the backend
before importing against an existing database with the old constraint.

## Extending providers

Keep provider retrieval in `smi_reconstruction.py` (`provider_holdings` and its
provider parser/dispatch). A new provider should emit the same validated holding
format: `etf_isin`, `as_of`, `name`, `isin`, `reported_weight` (NAV fraction), and
`estimate_type="provider_reported_equity_basket"`. Add it to the CLI provider
choices and dispatch; the database writer in
[holdings_db_import.py](../backend/app/services/holdings_db_import.py) is provider-independent.

## Offline tests

```shell
python -m unittest discover -s backend/tests -v
python astra/smi_reconstruction.py --self-test
```

The new unit tests use mocked database sessions and retrieval; they never connect
to PostgreSQL or modify live holdings.