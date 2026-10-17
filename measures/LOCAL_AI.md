# Sugestii AI locale, separate de regulile catalogului

## Rezultatul probei reale, 18 octombrie 2026

Ollama 0.40.5 portabil CPU și qwen2.5:1.5b au fost pornite efectiv local.
Promptul final measures-ai-3 a procesat cele trei articole: trei răspunsuri
complete structural, trei sugestii, cu pasajele verificate exact. Reluarea
offline a returnat aceleași sugestii din cache, fără apeluri la model.
Cele 22 de teste unitare trec; ele verifică implementarea, nu acuratețea AI.

**Calitatea modelului nu justifică recomandări automate.** A produs un fals
pozitiv pentru articolul despre controale și sugestii generale, slab formulate,
pentru cele două incidente. Unele câmpuri ating limita de caractere și sună
neterminat. Citatele reale nu demonstrează o legătură tehnică utilă. Nu s-a
aprobat nicio propunere și nu s-a publicat nimic pe hartă.

Livrabile: output/ai-real-pilot/ai_suggestions.json păstrează ieșirea, iar
pilot_review.json explică problemele per articol și limitele încercărilor
anterioare. Acesta este un test de integrare și diagnostic, nu un benchmark
independent sau o validare a recomandărilor. Un model mai capabil poate fi
selectat prin --model, după instalare și evaluare separată; nu este descărcat
automat de modul. Regula existentă rămâne sursa recomandărilor deterministe.

Modulul `measures.local_ai` folosește Ollama prin localhost. Nu modifică ai/,
scraping/, API-ul, frontend-ul sau datele de accidente. Nu necesită pachete Python
noi. Modelul se instalează separat; prima descărcare necesită internet, apoi
inferența și reluarea cache-ului sunt locale. Nu există tarif per apel API local.

## Pornire și test restrâns pe presă reală

Cu Ollama instalat și pornit și qwen2.5:1.5b descărcat:

Pe calculatorul acestei implementări, pachetul portabil CPU este în
measures/cache/ollama-cpu/, iar modelele în measures/cache/ollama-models/.
Acestea sunt locale și ignorate de Git. Pentru repornire în PowerShell:

```powershell
.\measures\start_local_ai.ps1
```

Pe alt calculator instalează [Ollama pentru Windows](https://docs.ollama.com/windows)
și descarcă [modelul local](https://ollama.com/library/qwen2.5:1.5b).
Scriptul de repornire nu instalează și nu descarcă nimic.

```powershell
ollama pull qwen2.5:1.5b
python -m measures.ai_run --output measures/output/ai-real-pilot --limit 3 --article-id press-cfd4d425b05574fbd870 --article-id press-4c90cf502cce2cbed684 --article-id press-fd82fd128c4b861174e4
```

Selecția este explicită: un articol despre controale (control negativ), un
incident din Podu Roș și un incident de lângă Lidl/Nicolina. Nu reprezintă un
eșantion de evaluare a acurateței. Se citește fișierul local deja colectat,
`scraping/predare_ai/articole_v2.json`; URL-urile publicațiilor nu sunt accesate.
Fără --article-id sunt citite primele --limit articole, care pot fi nerelevante.

Ieșirea trebuie să fie un director nou. Se salvează progresul după fiecare
articol. Timeout-ul sau răspunsul invalid produce eroare explicită și completed=false,
fără sugestii de rezervă prezentate ca AI; runner-ul continuă celelalte articole.
Indisponibilitatea inițială a serviciului oprește rularea. Rerularea într-un director nou folosește
cache-ul pentru articolele terminate; nu suprascrie ieșirea veche.

```powershell
python -m measures.ai_run --output measures/output/ai-replay --offline --limit 3 --article-id press-cfd4d425b05574fbd870 --article-id press-4c90cf502cce2cbed684 --article-id press-fd82fd128c4b861174e4
python -m unittest measures.test_local_ai -v
python -m measures.ai_verify
```

Modul offline nu contactează Ollama; un cache lipsă sau incompatibil este eroare.
Cache-ul, modelul și installer-ul nu intră în Git. Doar rezultatul pilotului
ai-real-pilot este permis ca livrabil de referință în measures/output/.

## Ce produce

`ai_suggestions.json` conține per articol:

- modelul, digestul modelului, versiunea promptului, hash-ul articolului și cheia cache;
- afirmația modelului privind relevanța, fără a o transforma în accident verificat;
- maximum o sugestie scurtă, inclusiv din afara catalogului (limită de pilot pe CPU);
- justificarea și verificările necesare în teren;
- pasajele exacte și pozițiile start/end în textul original;
- cost_ron=null, reduction=null, technical_sources=[];
- status=needs_human_review, location_id=null și in_iasi=null.

Articolul este împărțit în propoziții numerotate. Modelul returnează ID-uri,
iar codul atașează textul original al propozițiilor. Referințele inexistente,
câmpurile suplimentare de cost și procentele/prețurile generate sunt respinse.
Un pasaj existent nu dovedește că propunerea este tehnic adecvată: legătura
semantică, relevanța articolului și fezabilitatea necesită verificare umană.
Instrucțiunile eventual prezente în articol sunt tratate ca date în prompt;
acest lucru nu constituie o garanție că modelul nu poate fi influențat.

Promptul v3 limitează și lungimile câmpurilor, maximum două pasaje și două
verificări, pentru a reduce ieșirile trunchiate. Clasificarea relevanței rămâne
o afirmație a modelului, nu o verificare automată suficientă.

Nu sunt folosite coordonate OSM sau scoruri și nu se presupune că articolul
descrie una dintre trecerile scenariilor. Nu asociem costurile istorice prin
potrivirea liberă a titlului unei sugestii AI. Asocierea la catalog, sursele
tehnice și costarea sunt operații ulterioare, explicite.

## Cache și limite

Cheia include intrarea completă, promptul, schema, opțiunile, adresa locală și
digestul modelului. Online se recitește identitatea modelului instalat; offline
se folosește ultimul model-lock salvat. Răspunsurile sunt revalidate la reluare.
Nu sunt salvate în cache răspunsuri nevalide/trunchiate. Articolele peste 12.000
caractere sunt refuzate explicit, fără trunchiere ascunsă. Nu există verificare
token-cu-token că promptul încape în contextul modelului; astfel de texte trebuie
tratate separat înainte de producție. Nu se descarcă automat modele la rulare.
Sunt acceptate numai endpoint-uri loopback și modele locale listate de Ollama.

## Frontend ulterior

Acest fișier este o extensie separată, nu schema comună. Pentru afișare:
„Sugestie AI — necesită verificare”, textul propunerii, justificarea, citatele,
linkul articolului și lista verificărilor. Nu afișa pe hartă fără asociere
verificată la o locație și nu confunda aceste sugestii cu regulile deterministe.
