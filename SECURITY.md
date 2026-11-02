# Security

Do not report vulnerabilities with real personal documents. Treat uploaded files as hostile input. Production deployments should isolate document parsing, enforce size/type limits, encrypt private data, minimize retention and keep channel credentials narrowly scoped.

## Eigene API-Schlüssel (BYOK)

- Schlüssel kommen pro Anfrage im Header `X-LLM-Api-Key`. Sie werden nur im Arbeitsspeicher für diese Anfrage verwendet und nicht gespeichert oder geloggt. Fehlermeldungen und Tracebacks enthalten keine Request-Details.
- Die Weboberfläche legt den Schlüssel im `sessionStorage` ab, auf Wunsch im `localStorage`. Er wird nur an Endpunkte geschickt, die ein Sprachmodell nutzen. Jedes XSS auf der Web-Origin könnte ihn auslesen. Deshalb keine Fremd-Skripte einbinden und eine strikte Content-Security-Policy setzen.
- Eigene Endpunkt-URLs (`custom`) sind standardmäßig aus. Wenn ein Betreiber sie mit `BYOK_ALLOW_CUSTOM_BASE_URL=true` freigibt, akzeptiert der Server nur öffentliche HTTPS-Ziele und lehnt private, Loopback- und Link-Local-Adressen ab. Gegen DNS-Rebinding schützt diese Prüfung nicht vollständig. Ausgehenden Verkehr deshalb zusätzlich per Egress-Firewall begrenzen.
- Den Server nur hinter HTTPS betreiben, sonst gehen Schlüssel im Klartext über das Netz.
