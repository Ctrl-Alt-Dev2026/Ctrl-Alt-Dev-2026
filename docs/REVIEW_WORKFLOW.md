# Importul și verificarea locală — API v0.4

Backend-ul salvează articolul, extracția originală și candidații `pending`, apoi permite corectare și decizia explicită a operatorului. Aprobarea creează un eveniment canonic local; asocierea unui al doilea articol la acel eveniment păstrează un singur accident și ambele surse. Citirea pentru hartă prin `/api/v1/events` rămâne independentă: acest flux nu publică automat evenimente.

După review, [publicarea explicită din API v0.6](PUBLICATION_WORKFLOW.md) poate îngheța evenimentele eligibile și asocierea verificată la locații. Frontend-ul consumă rutele noi de publicații/locații; cititorul sintetic vechi rămâne separat.

## Pornire și stocare

Folosește comanda standard din [instrucțiunile locale](LOCAL_DEVELOPMENT.md). Rutele apar în secțiunea `review` din [Swagger](http://127.0.0.1:8000/docs). Sunt disponibile numai pentru conexiuni locale, pe host loopback și aceeași origine în browser. `operator` este un nume declarat pentru istoric, nu o identitate autentificată; această etapă nu introduce conturi sau acces la distanță.

Implicit, fișierele sunt `runtime/review/synthetic.json` și `runtime/review/observed.json`, ignorate de Git. Fiecare fișier conține importuri, candidați și evenimente canonice distincte. `SAFEIASI_REVIEW_DIR` poate selecta alt director de lucru înainte de pornire. Directoarele comune `false_data/`, `ai/`, `context/`, `risk/`, `coordonate/` și `.git/` sunt refuzate ca destinații.

MVP-ul folosește **un singur proces Uvicorn**, fără `--workers`. O blocare comună protejează tranzacțiile între fire și instanțe din acel proces; un fișier temporar în același director este sincronizat și înlocuiește atomic versiunea anterioară. Procesarea AI are loc înaintea tranzacției. Mai multe procese/laptopuri care scriu în același director nu sunt suportate. Fișierele persistă după restart; pentru backup, copiază directorul cu serverul oprit. Un fișier invalid produce 503 și nu este înlocuit automat cu unul gol.

## Operații

| Rută | Contract |
|---|---|
| `POST /api/v1/imports` | Articolul cu șapte câmpuri `2.0`, `pipeline`, `data_mode`, `operator`, `request_id`; 201 pentru import nou, 200 pentru repetarea identică |
| `GET /api/v1/imports/{import_id}` | Articolul integral, extracția istorică, modul de procesare și ID-urile candidaților |
| `GET /api/v1/candidates` | Listă; filtre `data_mode` și opțional `status=pending/approved/rejected/linked` |
| `GET /api/v1/candidates/{candidate_id}` | Articolul, câmpurile curente, extracția originală, istoricul și versiunea |
| `PATCH /api/v1/candidates/{candidate_id}` | `data_mode`, `expected_version`, `operator`, `reason`, `changes` |
| `POST /api/v1/candidates/{candidate_id}/review` | `data_mode`, `expected_version`, `operator`, `note`, `action=approve/reject/link` și verificările efectuate |
| `GET /api/v1/reviewed-events` | Evenimente canonice locale, cu versiunile, sursele și afirmațiile fiecărei surse |

La citire, `data_mode` este implicit `synthetic`; pentru date observate se cere explicit `?data_mode=observed`. La scriere, modul este obligatoriu în corp. Modul sintetic cere sursa `SINTETIC`, iar cel observat o sursă diferită; backend-ul verifică și modul rezultatului AI. O etichetă observată nu confirmă autenticitatea articolului sau exhaustivitatea presei.

Răspunsurile persistate au `response_origin: "stored_review"` și `publication_status: "not_published"`; extracția inclusă este istorică, chiar dacă rularea inițială a fost `live`. `processing_mode=cache` rămâne procesare din răspuns salvat. Reluarea sintetică explicită rămâne la rutele AI; `/imports` primește articolul integral și nu acceptă `mode=replay`.

## Reguli de import și corectare

- `request_id` conține 1–80 caractere alfanumerice, punct, cratimă sau underscore. Repetarea aceleiași cereri returnează importul existent, fără apel AI și fără resetarea corecturilor/deciziilor. Alt conținut cu aceeași cheie produce 409.
- Un `article_id` poate fi importat o singură dată în fiecare mod de date. Altă cheie pentru același articol produce 409; o nouă versiune a sursei necesită un ID explicit nou. Această protecție nu deduplică automat știri cu ID-uri diferite.
- Înaintea salvării sunt verificate starea neverificată, identificarea sursei, câmpurile și pasajele-dovadă, inclusiv offseturile în text. Geografia nu este copiată din fixture-uri. Un rezultat AI invalid produce 502, fără salvare.
- Indisponibilitatea AI produce 503 cu `persisted: false`, chiar dacă există fallback prin reguli. Cererea poate fi reluată. Operatorul poate alege explicit `pipeline=rules` pentru lucru fără model; rezultatul este etichetat corespunzător. Un rezultat fără candidați salvează importul și nu inventează un eveniment.
- `changes` poate modifica numai câmpurile din `CandidateFields`: data/ora accidentului, locul, participanții, cauza raportată, gravitatea, noaptea, coordonatele/precizia/municipiul și `location_evidence`. Identitatea, sursele, aprobarea, extracția originală și istoricul nu sunt editabile prin patch.
- Necunoscutele pot rămâne `null`/`necunoscut`; data accidentului nu este înlocuită cu data publicării. Coordonatele trebuie furnizate împreună, în limite globale, cu precizie `trecere/intersectie/segment`. Nu se generează automat pini. Acest API nu face geocodare sau verificarea limitei municipiului.
- Fiecare corectură salvează operatorul, momentul UTC, motivul și valorile înainte/după. Pasajele originale rămân alături de valorile originale; nu sunt prezentate automat drept dovezi pentru o valoare corectată manual.

## Decizia operatorului și duplicatele

`approve` și `link` cer `source_checked: true` și `duplicate_checked: true`, după verificarea efectivă de către operator. Dacă există coordonate sau un marcaj de municipiu cunoscut, se cere și `location_checked: true`; un pin cere în plus o explicație/sursă în `location_evidence`. `reject` cere operator și notă, fără să creeze un eveniment.

`approve` alocă un ID canonic nou. `link` cere `canonical_event_id` și `expected_event_version`: atașează candidatul la evenimentul existent în același mod de date și păstrează toate `article_ids`, `urls` și `source_claims`, inclusiv informații contradictorii sau lipsă. Câmpurile canonice nu sunt înlocuite în tăcere cu ale noului articol. Asocierea este o decizie umană, nu o concluzie a unei potriviri automate după dată/stradă.

Un candidat aprobat, respins sau asociat este finalizat și nu mai acceptă patch/review în acest MVP. Redeschiderea deciziilor, editarea ulterioară a evenimentului canonic și unirea a două evenimente deja aprobate sunt etape viitoare. O aprobare cu dată sau localizare necunoscută poate confirma relatarea, fără să o facă eligibilă pentru hartă. Setul observat nu este publicat prin cititorul sintetic.

## Exemplu sintetic în PowerShell

Exemplul folosește un articol existent, fără Ollama. Marcajele de verificare de mai jos sunt pentru demonstrația sintetică; pentru o sursă reală se completează numai după verificare.

```powershell
$base = 'http://127.0.0.1:8000'
function Invoke-SafeIasiJson($method, $path, $payload) {
    $json = $payload | ConvertTo-Json -Depth 30
    Invoke-RestMethod -Method $method -Uri "$base$path" -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($json))
}
$article = (Get-Content -Raw -Encoding utf8 false_data/articles.json | ConvertFrom-Json)[0]
$savedImport = Invoke-SafeIasiJson Post '/api/v1/imports' @{
    article = $article; pipeline = 'rules'; data_mode = 'synthetic'
    operator = 'Operator demo'; request_id = 'demo-syn-001-v1'
}
$candidateId = $savedImport.import.candidate_ids[0]
$candidate = (Invoke-RestMethod "$base/api/v1/candidates/$candidateId").candidate
```

Inspectează `article`, `original_extraction`, `fields` și `history`. Pe un candidat încă `pending`, o corectură demonstrativă care păstrează ora necunoscută:

```powershell
$changed = Invoke-SafeIasiJson Patch "/api/v1/candidates/$candidateId" @{
    data_mode = 'synthetic'; expected_version = $candidate.version
    operator = 'Operator demo'; reason = 'Exemplu sintetic: ora rămâne necunoscută.'
    changes = @{ ora = $null }
}
$reviewed = Invoke-SafeIasiJson Post "/api/v1/candidates/$candidateId/review" @{
    data_mode = 'synthetic'; expected_version = $changed.candidate.version
    operator = 'Operator demo'; note = 'Verificare demonstrativă pe date sintetice.'
    action = 'approve'; source_checked = $true; duplicate_checked = $true
}
Invoke-RestMethod "$base/api/v1/reviewed-events"
```

Rerularea exemplului de import reutilizează același import; un candidat deja finalizat nu trebuie corectat/aprobat din nou. Pentru un al doilea articol verificat despre același accident, folosește `action='link'`, ID-ul din `$reviewed.event.event_id` și versiunea curentă a evenimentului, în loc de o nouă aprobare.

## Erori și verificări

| Cod | Semnificație |
|---|---|
| 403 | Acces la review din afara laptopului, alt host sau altă origine |
| 404 | Import/candidat/eveniment inexistent în modul ales |
| 409 | Versiune veche, cheie/articol deja folosit sau candidat finalizat |
| 422 | Cerere/corectură/decizie invalidă ori verificare de localizare lipsă |
| 502 | Rezultat al extractorului neconform, inclusiv dovezi sau aprobare/geografie injectată |
| 503 | AI indisponibil ori stocare invalidă/inaccesibilă; operația nu este salvată |

Rulează cele două suite din [instrucțiunile locale](LOCAL_DEVELOPMENT.md#teste-și-audit). Testele verifică persistența la restart, idempotența, versiunile și concurența în același proces, scrierea atomică eșuată, păstrarea dovezilor, modurile de date separate și două articole asociate unui singur eveniment. Datele testelor sunt sintetice și temporare.

Verificare la 17 octombrie 2026: **48 teste backend și 42 teste AI trecute**, `pip check` fără probleme și 31 de linkuri relative verificate. Un server HTTP separat, cu stocare temporară, a parcurs importul celor patru articole sintetice existente, o corectură, două aprobări, o asociere și o respingere: două evenimente canonice, patru surse, aceleași rezultate după restart. Cererea repetată a produs 200/reutilizare, versiunea veche 409, modul observat a rămas gol, iar hash-urile fixture-urilor comune nu s-au schimbat. Stocarea testului a fost eliminată după oprirea acelui server; datele demo nu sunt încărcate automat în stocarea operatorului.

Extractorul prin reguli are încă falsuri pozitive la negații: textul de test „Campanie de prevenție pentru pietoni. Nu a avut loc un accident.” poate produce un candidat. Backend-ul îl păstrează neverificat și nu îl transformă într-un accident aprobat. Corectitudinea extracției pe presă reală rămâne de evaluat cu Emi; validarea JSON și existența citatului nu demonstrează că afirmația a fost interpretată corect.
