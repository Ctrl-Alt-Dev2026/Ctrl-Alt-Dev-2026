# SafeCross — investigație video locală

SafeCross implementează opțiunea 4 din [propunerile AI](../ai/AI_SAFETY_INVESTIGATOR_PROPOSALS.md): încărcare video → detecție AI → tracking → interacțiuni candidate → verificare umană → export. Este o extensie opțională; importul articolelor, review-ul și API-ul principal funcționează independent de instalarea video.

Un candidat semnalează proximitate persistentă în imagine. **Nu reprezintă automat un conflict rutier, un accident sau o locație periculoasă.** Un rezultat fără candidați este legitim și nu demonstrează siguranța locației.

## Pornire

Din rădăcina repository-ului, cu mediul virtual din [ghidul local](LOCAL_DEVELOPMENT.md):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-safecross.txt
.\.venv\Scripts\python.exe -m safecross.setup
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Deschide [interfața SafeCross](http://127.0.0.1:8000/safecross) sau [Swagger](http://127.0.0.1:8000/docs). Verifică disponibilitatea la `GET /api/v1/safecross/status`. Instalarea modelului este explicită; pornirea serverului nu descarcă modelul. Nu sunt necesare Ollama, conturi sau servicii plătite.

Instalează local FFmpeg și adaugă executabilele **`ffprobe` și `ffmpeg` în `PATH`**, apoi repornește terminalul/serverul. `ffprobe` este obligatoriu pentru verificarea timestampurilor înaintea inferenței. `ffmpeg` permite un preview MP4 în browser; fără acesta se servește fișierul încărcat, pe care browserul poate să nu-l decodeze. Dovezile JPEG și descărcarea AVI adnotat sunt disponibile separat. Comanda demo de mai jos necesită FFmpeg cu filtrele `vidstabdetect` și `vidstabtransform`.

## Demo reproductibil, cu filmare reală din Toronto

Cu serverul pornit, execută într-un al doilea terminal:

```powershell
.\.venv\Scripts\python.exe -m safecross.demo --submit
```

Comanda descarcă sursa publică, pregătește derivatul declarat, trimite o analiză reală și afișează URL-ul analizei. Clipul este `observed`, **nu este filmat în Iași** și nu este un exemplu sintetic de accident. Nu ajustăm filmarea sau pragurile pentru a fabrica un conflict.

Sursa este [Roncesvalles Avenue / Galley Avenue, Qviri, 15 iulie 2026](https://commons.wikimedia.org/wiki/File:Roncesvalles_Ave_crossing_at_Galley_Ave,_PXO_Type_A_lights_flashing,_July_2026.webm), publicată sub [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). [Fișierul original](https://upload.wikimedia.org/wikipedia/commons/0/06/Roncesvalles_Ave_crossing_at_Galley_Ave%2C_PXO_Type_A_lights_flashing%2C_July_2026.webm) rămâne separat de derivat. Atribuirea autorului, sursa, licența și modificările trebuie păstrate; derivatul este distribuit sub CC BY-SA 4.0.

Preprocesarea păstrează primele 12 secunde: redimensionare la 1280×720, stabilizare geometrică față de primul cadru, margini negre, resampling la 30 fps și eliminarea sunetului. Derivatul de detaliu decupează dreptunghiul `(x=400, y=300, lățime=640, înălțime=360)` din cadrul stabilizat, apoi îl afișează la 1280×720. Nu sunt generate persoane, vehicule sau porțiuni de stradă. Originalul este filmat din mână; nu îl prezentăm drept cameră fizic fixă.

ROI-ul demo, în coordonate normalizate ale **derivatului de detaliu**, este:

```json
[[0.10, 0.42], [0.70, 0.42], [0.70, 0.63], [0.10, 0.63]]
```

Verifică zona pe primul cadru. Pietonul traversează prin fața unui vehicul care așteaptă; aceasta poate fi o interacțiune benignă. SUV-ul alb din prim-plan parchează la altă adâncime și nu trebuie confundat cu vehiculul din dreptul trecerii. Numărul de candidați nu reprezintă un obiectiv de demo.

## Încărcare și verificare

În interfață, selectează clipul, operatorul, modul `observed` sau `synthetic` și confirmă un **cadru stabil**. `fixed_camera_confirmed=true` este declarația operatorului pentru o cameră fixă sau o stabilizare documentată; sistemul nu verifică automat stabilitatea. Alege o zonă a drumului care are sens în perspectiva filmării și completează proveniența.

API-ul acceptă un singur fișier multipart în `video`, plus `operator`, `data_mode`, `fixed_camera_confirmed=true`. Câmpurile opționale sunt `roi_json`, `source_url`, `attribution` și `license`; URL-ul sursei este metadată, nu declanșează descărcarea serverului. `roi_json` conține 3–12 puncte `[x,y]` între 0 și 1. Fără ROI este analizat întregul cadru, cu mai multe asocieri false posibile între planuri diferite.

Exemplu PowerShell pentru un clip local pregătit:

```powershell
$form = @{
    video = Get-Item '.\runtime\safecross-demo\roncesvalles-crossing-detail-12s-cfr30.mp4'
    operator = 'demo-operator'
    data_mode = 'observed'
    fixed_camera_confirmed = 'true'
    roi_json = '[[0.1,0.42],[0.7,0.42],[0.7,0.63],[0.1,0.63]]'
}
$job = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/safecross/jobs' -Form $form
$jobId = $job.job_id
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/safecross/jobs/$jobId"
```

Răspunsul inițial este HTTP 202. Stările sunt `queued`, `running`, `completed` și `failed`; recitește analiza pentru progres și eventualul cod de eroare. Rezultatele parțiale nu sunt publicate.

| Rută, după `/api/v1/safecross` | Utilizare |
|---|---|
| `GET /status` | Dependențe, model și limite |
| `POST /jobs` | Încărcare și inferență locală în coadă |
| `GET /jobs/{job_id}` | Progres, rezultate salvate, versiune și review |
| `GET /jobs/{job_id}/media/source` | Preview MP4 sau fișierul încărcat |
| `GET /jobs/{job_id}/media/annotated` | Descărcare MJPEG AVI adnotat, cu cadre eșantionate |
| `GET /jobs/{job_id}/media/poster.jpg` | Primul cadru adnotat |
| `GET /jobs/{job_id}/media/candidate-0001.jpg` | Dovada unui candidat existent; folosește numele din rezultat |
| `POST /jobs/{job_id}/candidates/{candidate_id}/review` | Decizie umană versionată |
| `GET /jobs/{job_id}/export` | JSON cu proveniență, model, parametri, cadre, track-uri și istoric |

Pentru un candidat existent, după `completed`, trimite JSON cu versiunea curentă a **analizei**:

```json
{"expected_version":1,"operator":"demo-operator","decision":"dismissed","note":"Am verificat secvența; asocierea este benignă sau neconcludentă."}
```

Decizia poate fi `confirmed` sau `dismissed`; confirmarea se referă la observația video verificată, nu certifică un accident. La HTTP 409 `video_version_conflict`, recitește versiunea înainte de o nouă decizie. Fiecare decizie păstrează operatorul, nota și istoricul. Review-ul nu creează evenimente de accident și nu publică automat pe hartă.

## Limite și interpretare

- Fișier: maximum **64 MiB**; extensii MP4, WebM, MOV, AVI sau MKV, cu decodare validă.
- Video: maximum **120 secunde**, **2.073.600 pixeli/cadru** și FPS între **1 și 120**, constant și verificabil. Extensia acceptată nu garantează că timeline-ul sau codecul sunt compatibile.
- Analiză: **5 cadre/secundă**, maximum **600 cadre eșantionate**; coada acceptă maximum **3 analize active/în așteptare**, procesate de un singur worker local.
- Coordonatele `bbox` sunt `[stânga, sus, dreapta, jos]` în pixeli ai fișierului încărcat. ROI folosește `[x,y]` normalizat; acestea nu sunt coordonate GeoJSON sau puncte geocodate.
- Timpul este `frame_index / source_fps`. Înaintea inferenței, [FFprobe](https://ffmpeg.org/ffprobe.html) verifică toate timestampurile, originea zero, FPS constant, durata și numărul cadrelor, cu maximum 20 secunde de preflight. La final, FPS-ul, dimensiunile și numărul cadrelor decodate trebuie să coincidă. Toleranța și eroarea maximă sunt exportate în `result.timing`; rezoluția temporală prea grosieră, VFR și timestampurile invalide produc `failed`, fără rezultat parțial. Chiar un AVI CFR poate necesita reexport MP4 CFR cu timeline precis. Conversia trebuie declarată; un interval între eșantioane poate ascunde o interacțiune.
- Detecțiile AI și tracking-ul simplu pot lipsi, se pot dubla sau pot schimba identități la ocluzie. Euristicile care elimină vehicule aparent staționare și posibili bicicliști/motocicliști reduc zgomotul, dar pot elimina cazuri relevante.
- Proximitatea se calculează determinist din separarea dreptunghiurilor în imagine, raportată la diagonala imaginii. Perspectiva poate apropia aparent participanți aflați în planuri diferite; ROI și verificarea secvenței sunt esențiale.
- Fără calibrare și validare adecvată nu raportăm metri, viteze, TTC, PET, probabilități de accident sau accidente evitate. Vezi [modelul plan–imagine în OpenCV](https://docs.opencv.org/4.x/d9/dab/tutorial_homography.html) și [contextul FHWA SSAM](https://www.fhwa.dot.gov/publications/research/safety/08049/); SSAM pentru microsimulare nu validează acest prototip cu pietoni.

## Model, stocare și reproducere

Detecția folosește **YOLOX Nano ONNX, release `0.1.1rc0`, intrare 416×416**, pe CPU prin OpenCV DNN. Clasele păstrate sunt persoană, bicicletă, automobil, motocicletă, autobuz și camion. Preprocesare: BGR float32 0–255, letterbox în stânga sus cu padding 114; decodarea exportului brut este fixată la `[1,3549,85]`. Nu schimbăm arbitrar modelul ONNX cu alt export.

[Checkpoint oficial](https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.onnx), SHA-256 verificat la instalare și utilizare:

```text
c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d
```

Surse: [contractul ONNX YOLOX](https://github.com/Megvii-BaseDetection/YOLOX/tree/main/demo/ONNXRuntime), [licența Apache 2.0 a proiectului](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/LICENSE), [OpenCV DNN pentru YOLO](https://docs.opencv.org/4.x/da/d9d/tutorial_dnn_yolo.html). Modelul, versiunea runtime-ului, parametrii și hashul clipului sunt în rezultatul exportabil; scorul detectorului nu este probabilitatea unui accident.

Datele locale sunt în `runtime/safecross`, modelul în `runtime/models`, iar fișierele demo în `runtime/safecross-demo`. Directoarele sunt ignorate de Git; nu se comit filmări, greutăți sau date personale. Configurare alternativă: `SAFEIASI_SAFECROSS_DIR` și `SAFEIASI_SAFECROSS_MODEL`. Rularea este locală, cu un proces Uvicorn și un worker video; nu este o instalare publică multiutilizator.

Un upload nou pornește inferență nouă. Citirea unei analize sau redarea artefactelor returnează **rezultate salvate**, marcate `response_origin: stored_analysis`; nu reprezintă procesare live repetată. La restart, analizele întrerupte sunt marcate `failed`, iar rezultatele terminate și review-urile rămân disponibile. Modurile `observed` și `synthetic` sunt păstrate explicit, fără conversie automată în accidente.

## Verificare

`requirements-dev.txt` include dependențele video pentru suita completă. Testele automate folosesc detecții/clipuri sintetice și preflight simulat; nu necesită descărcarea modelului sau filmări externe:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s ai/tests -v
```

Verificarea din 17 octombrie 2026: **95 teste backend/video + 42 teste AI trecute**, `pip check` fără conflicte. Separat, demo-ul pregătit de la sursa publică a rulat cu modelul real: 12 secunde, 360 cadre CFR verificate și 60 cadre eșantionate. Au fost verificate în browser uploadul, overlay-ul, saltul la candidat, review-ul, exportul, restaurarea rezultatului și afișarea mobilă. Un candidat a rămas în ROI-ul trecerii; acesta este un rezultat al exemplului, nu o metrică de acuratețe sau o dovadă a unui conflict rutier.
