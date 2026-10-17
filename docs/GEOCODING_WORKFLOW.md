# Geocodare înainte de aprobare — API v0.7

Backend-ul conectează [modulul offline de coordonate](../coordonate/README.md) la candidații din [review](REVIEW_WORKFLOW.md). Sugestia se cere pentru un candidat **pending**, se verifică de operator și se aplică separat. Aprobarea și [publicarea](PUBLICATION_WORKFLOW.md) rămân decizii distincte. Nu sunt necesare dependențe noi, chei sau rețea. Indexul este citit numai la cerere; fișierele colegului rămân nemodificate.

## Contract pentru frontend

Rutele sunt locale, din aceeași origine. Trimite întotdeauna `data_mode` explicit.

| Operație | Cerere / rezultat |
|---|---|
| `GET /api/v1/candidates/{id}?data_mode=observed` | Câmpuri, articol original, versiune și istoric |
| `POST /api/v1/candidates/{id}/geocoding/preview` | `{data_mode, expected_version}` → `proposal`; fără scriere |
| `POST /api/v1/candidates/{id}/geocoding/apply` | `{data_mode, expected_version, suggestion_id, operator, reason, location_checked:true}` → candidat actualizat, încă `pending` |
| `POST /api/v1/candidates/{id}/review` | Aprobare/respingere/asociere separată, cu noua versiune |

Propunerea include `candidate_id`, `expected_version`, `loc_text` exact, `current_location`, `proposed_changes`, `report`, `provenance`, `suggestion_id`, avertismente și `needs_operator_confirmation:true`. Raportul păstrează metoda, încrederea euristică, referințele OSM, punctul orientativ și verificările necesare. Proveniența păstrează hash-urile inputurilor și algoritmului, data indexului și limita administrativă. Încrederea nu este o probabilitate validată.

Frontend-ul afișează comparația și dovezile înainte de aplicare, fără bifarea automată a confirmării. Serverul recalculează sugestia din datele proprii și compară identificatorul; clientul nu trimite coordonate sau raport. Orice versiune, text sau input schimbat invalidează propunerea. Este o verificare de consistență; operatorul rămâne declarat, fără autentificare nouă.

Aplicarea este o corectură atomică. Raportul, proveniența și modificările aplicate se arhivează în `history[].changes.geocoding.after`; nota integrală este păstrată în istoric. `location_evidence` conține o referință scurtă la verificarea declarată și OSM. `original_extraction` nu se schimbă. Repetarea cu versiunea veche primește 409.

## Precizie și moduri de date

| Rezultat | Comportament |
|---|---|
| `trecere`, `intersectie`, `segment` | Coordonate propuse; operatorul verifică sensul textului și poziția |
| `strada` | Punct reprezentativ numai în raport; `lat/lon=null` pe candidat |
| `vag` | Fără pin precis; necunoscutele rămân necunoscute |
| Candidat finalizat | Preview/aplicare refuzate; evenimentul aprobat nu se rescrie |
| `synthetic` | 422 `synthetic_geocoding_unavailable`; OSM observat nu se aplică evenimentelor fictive |

Contextul publicării observate conține **treceri**. Intersecțiile și segmentele nu devin automat eligibile. Pentru o trecere, operatorul verifică ID-ul OSM în `/api/v1/publication-context?data_mode=observed&q=...`, apoi asociază explicit locația la publicare. Nu se selectează automat cel mai apropiat punct.

Schimbarea `loc_text` prin PATCH golește vechile `lat`, `lon`, `precizie_loc`, `in_iasi`, `location_evidence`, cu istoric. Un set nou coerent poate fi furnizat explicit în același patch; valorile omise nu sunt moștenite din localizarea veche. Recomandarea CLI a colegului de a geocoda după aprobare rămâne o diferență documentată; integrarea API lucrează înainte de aprobare. Nodurile cunoscute neverificate nu sunt folosite.

## Exemplu local

Folosește un candidat observat importat legitim; exemplul nu creează accidente reale.

```powershell
$base = 'http://127.0.0.1:8000'
$candidateId = '<ID din import>'
$candidate = (Invoke-RestMethod "$base/api/v1/candidates/${candidateId}?data_mode=observed").candidate
$body = @{ data_mode='observed'; expected_version=$candidate.version } | ConvertTo-Json
$proposal = (Invoke-RestMethod -Method Post -Uri "$base/api/v1/candidates/$candidateId/geocoding/preview" -ContentType 'application/json' -Body $body).proposal
$proposal | ConvertTo-Json -Depth 20
```

Numai după verificarea articolului, poziției, referințelor OSM și avertismentelor:

```powershell
$body = @{
  data_mode='observed'; expected_version=$candidate.version
  suggestion_id=$proposal.suggestion_id; operator='Mihnea'
  reason='<ce ai verificat efectiv în sursă și OSM>'
  location_checked=$true
} | ConvertTo-Json
$updated = (Invoke-RestMethod -Method Post -Uri "$base/api/v1/candidates/$candidateId/geocoding/apply" -ContentType 'application/json' -Body $body).candidate
```

Folosește `$updated.version` pentru review; verificările sursei și duplicatelor rămân obligatorii.

## Erori și verificare

422 indică mod/text/confirmare invalide; 409 indică versiune depășită, candidat finalizat sau propunere schimbată; 503 indică index invalid/lipsă ori algoritm schimbat. Pentru `geocoding_restart_required`, verifică schimbarea și repornește serverul. 403 indică acces din altă origine sau din afara calculatorului.

Testele folosesc surse fictive și stocare temporară, inclusiv pentru simularea contractului `observed`; nu constituie un set de accidente reale. Verifică publicarea unei treceri până la export, respingerea străzii pentru clasament, concurența și păstrarea dovezilor.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_geocoding*.py' -v
```

Pe laptopul verificat, Ollama și modelul `qwen2.5:1.5b` nu sunt instalate. Geocodarea, regulile și reluările etichetate funcționează independent; extracția textului prin model necesită pregătirea separată din [modulul AI](../ai/README.md).

Validarea integrării v0.7: **244 teste trecute** — 158 backend/video/publicare/geocodare, 42 extracție, 21 tipare și 23 context/scor. Cele 19 teste noi acoperă adaptorul offline și fluxul HTTP până la export. Cele 43 de verificări CLI ale modulului colegului sunt consemnate separat; nu sunt incluse în acest total.
