# Colectare periodică, fără lansare manuală la fiecare actualizare

Scraperul are două utilizări: parcurgerea istorică (coada persistentă) și verificarea noutăților. Simplul fapt că îl lansezi repetat nu actualiza listările deja salvate; de aceea există acum --noutati.

Exemplu din rădăcina repository-ului:

    python -m scraping.scraper_stiri --noutati --de-la 2026-01-01 --pauza 15 --max-taskuri 100

Data finală se calculează la fiecare rulare; nu o fixa la ziua demo-ului într-o sarcină recurentă. Modul reîncarcă primele listări Local, urmează paginile consecutive cu URL-uri noi și oprește extinderea la o pagină ale cărei carduri sunt deja în inventar. Păstrează articolele descărcate și procesează și taskurile de articol rămase în coadă. Nu folosește --actualizeaza, care ar rearma și articolele vechi.

Această optimizare presupune liste cronologice. Nu garantează descoperirea unui articol inserat ulterior pe o pagină veche, corectarea unui body deja descărcat sau refacerea întregii arhive. Pentru arhivă folosește modul obișnuit. Dacă bugetul expiră sau domeniul este în pauză, taskurile rămân în coadă pentru următoarea rulare; verifică raport.json.

## Windows Task Scheduler

Nu a fost instalată automat o sarcină Windows și nu rulează încă un programator periodic.

Pentru programare locală:

1. Deschide Task Scheduler și creează o sarcină, de exemplu „SafeIasi colectare presă”.
2. Alege un trigger zilnic, repetat la 6 ore, ca exemplu de frecvență. Poți alege alt interval în funcție de accesul acceptat de surse.
3. La acțiune selectează calea absolută a executabilului Python din mediul în care ai instalat scraping/requirements.txt.
4. Argumente: -m scraping.scraper_stiri --noutati --de-la 2026-01-01 --pauza 15 --max-taskuri 100
5. Start in: C:\Users\teodo\Desktop\Ctrl-Alt-Dev-2026
6. La rulări suprapuse alege „Do not start a new instance”. Laptopul trebuie să fie pornit și conectat; configurează separat execuția după un trigger ratat, dacă dorești.

Nu rula simultan alt scraper în același director. Respectă pauzele și blocările sursei; programarea nu le ocolește. Pentru a exclude temporar BZI, adaugă --surse zdi.

După colectare, textele se curăță și se exportă local:

    python -m scraping.curata_si_exporta_articole --intrare scraping/data/candidati.csv --director scraping/data/predare_periodica

Fișierul demo din scraping/predare_ai/ rămâne un set fix de 94 de articole. Nu este rescris de comanda de mai sus. Poți programa conversia după terminarea colectării. Integrarea AI și selecția articolelor eligibile sunt etape separate, realizate de utilizator după export. Scrapingul nu lansează aceste etape și nu publică automat evenimente pe hartă.

## Ce poți spune la demo

„Am implementat colectarea incrementală din surse de presă, cu deduplicare, cache, reluare și export pentru modulul AI. Rularea poate fi programată periodic. Pentru demonstrație folosim un set fix colectat anterior, iar extracțiile și localizările necesită verificare.”

Poți spune „rulează automat la fiecare X ore” numai după ce ai configurat programatorul și ai verificat o execuție. Declanșarea manuală la demo este compatibilă cu un proces automatizabil; nu pretinde că programarea sau validarea există deja dacă nu sunt configurate.
