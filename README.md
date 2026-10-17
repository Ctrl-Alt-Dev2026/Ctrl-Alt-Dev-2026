# SafeIași

SafeIași este numele de lucru al unui proiect pentru Hackathon AI Iași 2026 (16–18 octombrie), realizat de o echipă de șase persoane. Produsul propus ajută administrația să identifice locațiile de verificat prioritar pentru siguranță rutieră, pe baza unor evenimente documentate, extrase cu AI și verificate de operator.

Clientul vizat este Primăria Iași; nu există un contract sau un parteneriat confirmat. Repository-ul conține documentație, fixture-uri sintetice în `false_data/` și un audit al acestora, fără aplicație sau set de accidente reale verificat.

- [Contextul proiectului, principiile și diferențele dintre planuri](docs/PROJECT_CONTEXT.md)
- [Responsabilitățile și planul de lucru pentru backend](docs/BACKEND_WORK_PLAN.md) — Mihnea: backend/API, provizoriu; Emi: extracție AI.
- [Planul inițial pentru șase persoane și aproximativ 25 de ore](docs/HACKATHON_PLAN.md) — atașamentul păstrat integral; observația despre accesul GitHub din introducere este istorică.
- [Planificarea existentă: „Harta pietonului – Iași · Plan v2”](Planificare.md) — păstrată integral; conține propuneri care diferă de planul SafeIași.

Primul pas backend este auditul fixture-urilor, fără dependențe externe:

```powershell
python -m api.validate_fixtures false_data
python -m unittest discover -s tests -v
```

Auditul întoarce codul `1` când găsește probleme; fixture-urile actuale au neconcordanțe documentate în plan. Acesta nu validează date observate și nu reprezintă un API implementat. Calendarul se recalculează de la ora reală de pornire, raportat la [predarea din 18 octombrie, 16:30–17:00](https://markaiintegrator.ro/hackathon-ai/), în fusul Europe/Bucharest.
