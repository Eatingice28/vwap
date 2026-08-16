# Validation Notes

## Browser Demo-mode smoke test

On 2026-08-16, the dashboard was launched locally with its default **Demo mode** and opened successfully in a browser. It rendered the `NVDA, AMD` watchlist, SPY/QQQ shared context, the VWAP/detail table, and the selected-symbol price-versus-VWAP chart. The page showed only synthetic data and educational, non-instructional wording. No Streamlit exception was shown.

## Offline test status

`tests/static_and_simulated_checks.py` passed compilation, collector import-policy inspection, simulated collector JSON contract validation, dashboard Webull-feed parsing, and Demo-mode VWAP/premarket calculations. The test did not call a live provider or use any credential.

## Known verification boundary

The maintained Webull SDK dependency could not be installed in this sandbox without a C++ compiler because its legacy `grpcio-tools==1.51.1` dependency requires a native build. Per user instruction, actual SDK authentication, account entitlement, and production premarket-bar availability remain manual VPS validation steps.
