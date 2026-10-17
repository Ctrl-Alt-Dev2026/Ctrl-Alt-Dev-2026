# Folosirea ChatGPT în browser, fără API

## Variantă fără fișiere în conversație

Poți copia întregul conținut CHAT_MESSAGE.txt din pachet direct în chat.
Include promptul, schema și cele trei articole; cere răspuns JSON în conversație.
Nu mai atașezi nimic. Fișierele locale păstrează doar auditul și validarea.
Automatizarea independentă este în [BACKEND_HANDOFF.md](BACKEND_HANDOFF.md) și
poate folosi sesiunea fără cont dacă pagina permite. JSON-ul afișat trebuie
preluat și validat înainte de utilizare.

Exportul, importul și validarea rulează local, fără conexiuni de rețea.
Tu faci încărcarea în ChatGPT și salvezi rezultatul. Modulul nu automatizează
autentificarea, browser-ul sau conversația. Folosește limitele contului tău;
nu promite acces nelimitat sau calitate garantată.

## 1. Fișierele sunt deja pregătite

În `measures/output/chatgpt-package/` găsești:

- articles_packet.json — trei articole reale complete, surse și pasaje numerotate;
- response_schema.json — structura exactă a răspunsului cerut;
- PROMPT.txt — instrucțiunile de copiat în conversație.

În ChatGPT deschide o conversație nouă, atașează **articles_packet.json și
response_schema.json**, apoi copiază conținutul PROMPT.txt și trimite.
Nu este nevoie de fișierele din ai/.

Pachetul conține un articol despre controale, un incident din Podu Roș și unul
din Nicolina/Lidl. Nu oferim modelului rezultatele dorite. Articolele sunt
relatări nevalidate; nu au asociere verificată la trecerile scenariilor.

## 2. Salvează răspunsul

Cere fișierul descărcabil `chatgpt_response.json` (promptul cere deja acest lucru).
Salvează-l în `measures/cache/chatgpt_response.json`. Cache-ul este ignorat de Git.
Poți indica și o cale absolută către Downloads la import; fișierul este doar citit.
Dacă primești text în loc de fișier, salvează numai JSON-ul, fără delimitatoarele
Markdown de tip ```json, într-un fișier UTF-8.

Nu există încă un răspuns ChatGPT în repository. Fixture-urile testelor sunt
scrise manual pentru verificarea codului, nu rezultate AI reale.

## 3. Importă și validează

Din rădăcina repository-ului, în PowerShell:

```powershell
python -m measures.chatgpt_exchange import --response measures/cache/chatgpt_response.json --output measures/output/chatgpt-import-01
```

Opțional adaugă `--model-label "numele modelului afișat în ChatGPT"` pentru a
consemna ce ai folosit. Acesta este metadată declarată de operator, nu verificată
independent. Numele contului sau datele de autentificare nu sunt necesare.

Directorul de output trebuie să fie nou. Se produc:

- chatgpt_suggestions.json — date cu citate și poziții verificate, pentru review;
- original_response.json — JSON-ul original pentru audit.

Niciun fișier de input nu este suprascris. La răspuns invalid nu se creează un
export de sugestii; terminalul explică problema. Cere o corectură în aceeași
conversație și repetă importul. Nu modifica articolul ca să corespundă citatului.

## Ce verifică și ce nu verifică importul

Verifică ID-ul pachetului, toate cele trei articole fără duplicate, schema și
tipurile, lungimile, pasajele și citatele exacte în articolul corect. Un citat
poate fi un extras consecutiv de 20–600 caractere din pasaj, fără reformulare.
Respinge câmpuri suplimentare de cost, prețuri/procente generate și contradicția
relevant=false cu sugestii. Nu acceptă chei JSON duplicate sau NaN.

Nu poate demonstra că răspunsul chiar provine de la ChatGPT, că modelul a înțeles
corect articolul sau că o intervenție este adecvată. Toate sugestiile au
needs_human_review; costurile și reducerile rămân null, location_id și in_iasi
rămân null, iar numărul propunerilor aprobate este zero. Relevanța rămâne o
afirmație a modelului. Un citat real poate fi ales greșit semantic.

## Actualizarea pachetului după date noi

```powershell
python -m measures.chatgpt_exchange prepare --output measures/output/chatgpt-package-v2
```

La importul acelui pachet folosește și:
`--packet measures/output/chatgpt-package-v2/articles_packet.json`.
Un pachet este verificat contra sursei curente. Dacă un pull schimbă articolele,
regenerează pachetul și cere din nou analiza; nu se amestecă versiuni tacit.

## Teste și frontend

```powershell
python -m unittest measures.test_chatgpt_exchange -v
```

Frontend-ul poate consuma ulterior chatgpt_suggestions.json într-un panou de
review pe articol: title, rationale, checks, evidence[].quote și url. Nu este
schema comună și nu este legat automat de hotspot-uri. Nu există aprobare sau
publicare automată; datele observate și scenariile sintetice rămân separate.
Exportul de intrare chatgpt-package intră în Git; răspunsurile/importurile noi
sunt ignorate implicit până la o selecție explicită pentru livrare.
