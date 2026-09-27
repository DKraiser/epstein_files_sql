# **Z1: Z Hugging Face do vlastnej PostgreSQL databázy** 

|**Podmienka**|**Pravidlo**|
|---|---|
|Forma|Individuálne riešenie a krátka individuálna obhajoba.|
|Hodnotenie|15 bodov: jadro 12 bodov a jedno povinné rozšírenie 3 body.|
|Termín Z1|Do konca 4. výučbového týždňa, pred prednáškou 5. Presný dátum a čas je v zadaní v<br>Teams.|
|Priebežná kontrola C1|Po cvičení 2, pred prednáškou 3; samostatné 2 body, nezapočítavajú sa do 15 bodov Z1.|
|AI|Povolená. Za správnosť riešenia a jeho vysvetlenie zodpovedáte vy.|

## **1. Čo máte vytvoriť** 

Samostatne stiahnite určený dataset z Hugging Face, preskúmajte ho, navrhnite vlastnú relačnú schému a naprogramujte transformáciu a import do PostgreSQL. Nad importovanými dátami implementujte vyhľadávanie a analytické dopyty, zvoľte indexy a overte ich vplyv na vykonanie dopytov. Nakoniec dokončite jedno rozšírenie podľa kapitoly 9. 

Výsledkom nie je iba databáza, ktorá obsahuje riadky. Odovzdáte reprodukovateľný postup a dôkazy, z ktorých je zrejmé, prečo ste dáta modelovali a spracovali práve takto. 

**Schému a importér vytvárate vy.** Obnova školského dumpu, spustenie importéra z učiteľského riešenia alebo prevzatie databázy spolužiaka túto požiadavku nespĺňa. Knižnice, dokumentáciu a citované príklady používať môžete. Samoúčelne iné názvy tabuliek sa nehodnotia; vhodnú zdrojovú štruktúru nemusíte nasilu meniť. 

Neimplementujete OCR, nové rozpoznávanie entít, web scraping ani geokódovanie. Nevytvárate frontend. Pripravené geo dáta sa použijú až v ďalšom zadaní. 

## **2. Dáta: pevný zdroj a rozsah** 

Použite dataset kabasshouse/epstein-data a výhradne túto revíziu: 

`133ef9f0a539fafc270cde8fa8638dc38d89968d`
Zoznam súborov pevnej revízie je východiskom na stiahnutie. Nepoužívajte pohyblivé `main` alebo `latest` . 

Pre finálne Z1 stiahnite a spracujte všetky súbory `*-of-*.parquet` v týchto vrstvách: 

|**Adresár v repozitári**|**Súbory**|**Zdrojové riadky**|
|---|---|---|
|`data/documents/`|15|1 424 673|
|`data/chunks/`|11|2 193 090|
|`data/entities/`|18|10 629 198|
|`data/persons/`|1|1 614|
|`data/kg_entities/`|1|467|
|`data/kg_relationships/`|1|2 198|
|`data/derived_events/`|1|3 038|
|`data/event_participants/`|1|5 751|
|`data/event_sources/`|1|21 910|
|`data/financial_transactions/`|1|49 770|
|`data/curated_docs/`|1|5 766|
|`data/provenance/runs/`|1|123|
|`data/provenance/files/`|3|1 387 775|

Spolu je to **56 Parquet súborov, približne 1,45 GB komprimovaného vstupu** . Databáza, indexy, rozbalené texty a pracovné súbory zaberú ďalšie miesto. Veľkosť stiahnutia nie je veľkosť databázy a nemusíte ju umelo zväčšovať na 20 GB. 

Zdroj obsahuje aj paralelné exporty bez `-of-` , napríklad `persons-00000.parquet` . Tie do Z1 nepridávajte. Nekontrolované načítanie všetkých `*.parquet` môže zdvojiť dáta. Embeddingy, audit log a ostatné neuvedené vrstvy nie sú povinným vstupom. Priložte si aj zdrojové `README.md` , `LICENSE` a `PROVENANCE.md` z rovnakej revízie. 

Sťahovanie automatizujte a zdokumentujte. Použiť môžete napríklad `huggingface_hub` alebo `hf download` ; oficiálny návod vysvetľuje výber revízie a súborov. Po stiahnutí musí import vedieť pracovať offline. Ak pevná revízia nie je dostupná, kontaktujte cvičiaceho; nemeňte dataset svojvoľne. 

### **Význam a neistota dát** 

Dokument, textový chunk, extrahovaná zmienka a overená identita sú rôzne objekty. Vrstva `entities` obsahuje extrahované zmienky, nie automaticky overené osoby. Rovnaké meno nemusí označovať rovnakú osobu. Výskyt v dokumente ani spoločný dokument nedokazujú osobný vzťah, stretnutie alebo protiprávne konanie. 

Zdrojové súbory uchovajte nezmenené. Dataset môže obsahovať citlivý a znepokojujúci obsah; na technické overovanie používajte prednostne ID, metadáta a agregáty. Plné dokumenty, dataset, heslá a tokeny nevkladajte do verejného Git repozitára ani verejných AI služieb. Potrebné malé dôkazy odovzdávajte iba v rámci predmetu. 

## **3. Postup počas semestra** 

|**Kedy**|**Čo máte rozpracovať**|
|---|---|
|Cvičenie 1|Rozbehnúť PostgreSQL, pripojiť sa, preskúmať dva zdrojové súbory a podľa času začať<br>importér. Hotový import sa nevyžaduje.|
|Cvičenie 2|Dokončiť malý vlastný import, kontroly, jeden FTS dopyt a GIN. Po cvičení odovzdať C1<br>podľa kapitoly 4.|
|Týždeň 3|Cvičenie patrí PostGIS. V Z1 samostatne rozšíriť import na celý vstup a pripraviť vlastné<br>dopyty.|
|Týždeň 4|Dokončiť kontroly, indexy, jedno základné porovnanie a rozšírenie; do konca týždňa<br>odovzdať Z1. Cvičenie naďalej patrí PostGIS a C2.|
|Cvičenia 5-6|Nad už odovzdanou databázou sa učiť detailné plány a optimalizáciu pre výkonovú časť<br>Z2. Z1 sa druhýkrát neodovzdáva.|



Každé cvičenie nasleduje po rovnako očíslovanej prednáške. C1 a Z1 sú míľniky toho istého riešenia, nie dva nezávislé projekty. Skripty a schému ďalej rozvíjajte. 

## **4. Checkpoint C1: malý import, FTS a jeden GIN** 

**Táto kapitola sa odovzdáva až po cvičení 2. Nie je to zoznam povinností na koniec prvého cvičenia.** Maximum je 2 body; presný čas odovzdania je v Teams. 

### **Spoločná vzorka** 

Pre C1 stačia tieto dva súbory z revízie určenej v kapitole 2, spolu približne 75 MB: 

```
data/documents/documents-00000-of-00015.parquet
data/chunks/chunks-00000-of-00011.parquet
```

Vlastným skriptom vytvorte vzorku `c1-sample-v1` : 

1. Z uvedeného dokumentového súboru vyberte 1 000 riadkov s najnižším číselným `id` ; použite explicitné usporiadanie. 

2. Z uvedeného chunkového súboru vyberte všetky chunky, ktorých `document_id` patrí medzi tieto dokumenty. 

3. Importujte ich do vlastného modelu dokument/chunk. Očakávame 1 000 dokumentov a 160 chunkov, ktoré odkazujú na 157 rôznych dokumentov. Zdrojové ID dokumentov sú 1 až 1 000. 

Nejde o všetky chunky týchto dokumentov v celom zdroji. Dokument bez chunku v tejto vzorke nemusí byť dokument bez textu. Nevyberajte náhodných 1 000 chunkov a vzorku nepoužívajte na závery o výkone veľkého datasetu. 

Pri dokumente zachovajte zdrojové ID, `file_key` , dataset a typ. Pri chunku zdrojové ID, odkaz na dokument, poradie a text. Názvy tabuliek sú vaše. Vytvorte PK/UNIQUE a validovaný FK chunk/dokument. Overte počty, duplicity a osirelé odkazy. Opakované spustenie nesmie neúmyselne zdvojiť dáta; prípustný je aj čistý rebuild vlastnej schémy. 

### **Vyhľadávanie** 

Nad importovanými chunkmi implementujte tento predikát, prispôsobený názvom vašej schémy: 

```
to_tsvector('english', coalesce(content, ''))
```

- `@@ plainto_tsquery('english', 'flight')` 

Výstup sú zdrojové dvojice `(chunk_id, document_id)` , usporiadané podľa `chunk_id` , bez `LIMIT` a bez zlučovania viacerých chunkov jedného dokumentu. 

1. Spustite dopyt bez pomocného FTS indexu a uložte celý malý výsledok. 

2. Vytvorte jeden GIN kompatibilný s použitým výrazom na fyzickej tabuľke. 

3. Zopakujte dopyt a porovnajte všetky výsledkové dvojice, ich počet a poradie. 

4. Uložte základný `EXPLAIN` pred/po, definíciu a veľkosť indexu. Stačí pomenovať scan a prípadné triedenie, bez rozboru cost, loops alebo BUFFERS. 

5. Na oddelených literáloch `flight` , `flights` , `preflight` porovnajte FTS s `ILIKE '%flight%'` a vysvetlite odlišný význam. 

Nulový výsledok na vzorke môže byť správny; literály overia aj kladný a záporný prípad. Sekvenčný scan je prípustný. Nemusíte dosiahnuť zrýchlenie, index nevynucujte a nepridávajte umelé kópie riadkov. PK/UNIQUE/FK ostávajú aktívne. 

### **Vysvetlenie a odovzdanie C1** 

Do `C1/run.md` napíšte postup, stručné mapovanie ID/polí a štyri návrhové riadky: presný lookup podľa `file_key` , substring, JSONB containment a časový rozsah v append-only logu. Pri každom uveďte operátor, vhodný index alebo žiadny index a jedno riziko. Ďalšie štyri indexy ani logovú tabuľku neimplementujete. 

Priložte manifest dvoch súborov s repo/revíziou, cestami a SHA-256, vlastné DDL/importér, kontrolné a vyhľadávacie SQL, malé výsledky a základné plány. V `run.md` stručne overte jedno tvrdenie AI; ak AI nepoužijete, tvrdenie na overenie vám poskytne cvičiaci. Rozsiahly report, plný ER diagram, desať behov ani p50/p95 sa v C1 nevyžadujú. 

Pri obhajobe vysvetlíte vlastné riešenie a jeden súvisiaci mechanizmus z prvej prednášky. Nevyžaduje sa samostatný benchmark JOINov či TOAST. 

|**Oblasť C1**|**Body**|
|---|---|
|Vlastný import, mapovanie ID a integrita|0,5|
|Správny FTS a odlíšenie od substringu|0,5|
|Kompatibilný GIN, zhodný výsledok a základný náhľad prístupu|0,5|
|Operátor/index, interný mechanizmus a trade-off|0,5|

## **5. Finálne jadro: prostredie, profilovanie a import** 

Nasledujúce kapitoly patria do finálneho Z1. Malý C1 filter pri plnom importe odstráňte; vzorku nepripočítavajte druhýkrát. 

### **Reprodukovateľnosť** 

Použite PostgreSQL v kontajneri alebo rovnako reprodukovateľnom prostredí. Uveďte verzie servera, rozšírení a knižníc. Priložte konfiguráciu alebo presný postup inštalácie. Download, transformácia, import a validácia sa musia dať zopakovať príkazmi alebo skriptmi od prázdnej pracovnej databázy, aj offline nad získaným vstupom. 

V `source-manifest.json` evidujte repo ID, celý commit SHA, čas získania a verziu sťahovacieho nástroja. Pre každý z 56 súborov uveďte cestu, bajty, SHA-256 vypočítaný z obsahu a počet riadkov. Kontrolujte úplnosť shardov a pred importom zhodu s manifestom. 

Študentské materiály | 14. 9. 2026 

### **Profilovanie** 

V `data-profile.md` doložte aspoň pre documents, entities, event_sources, financial_transactions a provenance/files schému zdroja, počty, NULL/prázdne hodnoty, kandidátne kľúče, duplicity a nevyhovujúce odkazy. Výsledky zistite vlastnými skriptmi. DuckDB, Polars či PyArrow môžete použiť na prácu s Parquet; cieľ zostáva PostgreSQL. 

### **Import a chyby** 

- Použite dávky alebo streamovanie, prípadne zdôvodnite iný pamäťový postup. Celý textový korpus nemusí byť naraz v RAM. 

- Zachovajte dohľadateľnosť: zdrojová vrstva/súbor a pôvodné ID alebo pozícia riadka. 

- Chybné dátumy, JSON, sumy alebo odkazy evidujte v error logu či karanténe. Nezamieňajte chybu s chýbajúcou hodnotou a potichu nezahadzujte dáta. 

- Pre každú vrstvu doložte `N_read = N_accepted + N_quarantined + N_duplicate` . Kategórie sa neprekrývajú a duplicity musia mať dôvod. Počty cieľových riadkov po normalizácii vykazujte samostatne. 

- Preukážte bezpečné opakovanie: idempotentný import alebo dokumentovaný rebuild vlastnej pracovnej schémy. Vysvetlite aj postup po prerušení. 

- Na konci automaticky overte kľúče, FK, počty a súlad so zdrojom. Dobehnutie skriptu bez výnimky nie je dostatočný dôkaz. 

- Vlastné importné behy evidujte oddelene od upstream `provenance/runs` ; ide o rozdielne procesy. 

## **6. Finálne jadro: vlastná schéma a integrita** 

Model musí pokrývať význam všetkých 13 vrstiev z kapitoly 2. Názvy a počet cieľových tabuliek volíte vy. Zdôvodnite hranice tabuliek, normalizáciu alebo denormalizáciu, dátové typy, kľúče a miesto pre JSONB. Jeden univerzálny JSONB stĺpec bez relačného modelu nestačí. Nevyžaduje sa však delenie vhodnej tabuľky len kvôli odlišnosti. 

Odovzdajte ER diagram alebo rovnako čitateľný opis modelu a `data-mapping.md` : 

```
zdrojova vrstva/pole | cielova tabulka/pole | prevod a typ
NULL/chyba | kluc/vazba | dovod rozhodnutia
```

Popíšte každé využité pole; nevyužité polia uveďte s dôvodom. Povinné dopyty nesmú stratiť potrebné dáta len kvôli jednoduchšiemu importu. Pôvodné súbory zostávajú zachované. 

Povinne vyriešte a vysvetlite: 

1. Pôvodné ID a jeho menný priestor verzus vlastné surrogate ID. Pri prečíslovaní zachovajte jednoznačné mapovanie; poradie importu nie je stabilná identita. 

2. Zdrojové `entities.document_id` zachovajte ako `raw_document_id` alebo ekvivalent. Nullable FK na dokument určujte samostatne; rovnaký názov stĺpca nepreukazuje rovnaký menný priestor. 

3. Pri dátumoch rozlišujte chýbajúci údaj, chybu prevodu a neurčenú presnosť. Nevymýšľajte konkrétny deň alebo časové pásmo. 

4. Pri `documents.email_fields` rozlíšte pôvodný zápis, JSONB, SQL NULL, JSON null, chýbajúci kľúč a neplatný JSON. Automatický cast bez obsluhy chýb nestačí. 

5. Pri sumách zachovajte dostupnú presnosť, znamienko a menu. Neznáma suma nie je nula; rôzne meny nesčítavajte bez pravidla. 

6. Zachovajte pôvodný text zmienky. Vlastnú normalizáciu označte pravidlom/verziou; normalizovaný reťazec nie je overená identita. 

### **Cudzie kľúče sú povinné** 

FK musia byť skutočne deklarované cez `FOREIGN KEY` / `REFERENCES` , aktívne a validované voči finálnym dátam. Názov `*_id` , čiara v diagrame ani kontrola len v aplikácii nestačia. 

Minimálne zabezpečte tieto logické väzby v názvoch svojej schémy: 

- chunk na dokument; 

- zdrojová aj cieľová entita KG vzťahu na KG entitu; 

- účastník udalosti na udalosť; 

- zdroj udalosti na udalosť. 

FK doplňte aj pre ostatné skutočné referencie vrátane mapovacích tabuliek. Pri každej väzbe zdôvodnite povinnosť/voliteľnosť a správanie pri zmene či zmazaní rodiča. 

**Nečisté vstupy nie sú dôvod na odstránenie FK z celého modelu.** Pri unresolved väzbe uchovajte pôvodnú hodnotu a explicitný stav; cieľové ID môže byť NULL, ale nenulová hodnota musí mať FK. Osobitne vysvetlite, prečo `event_sources.file_key` nemusí byť povinný platný odkaz na dokument a prečo meno účastníka nemožno automaticky považovať za `person_id` . 

### **Istota párovania** 

Pri párovaní odporúčame evidovať `match_method` , `match_status` , zdroj/cieľ, zdôvodnenie a `match_confidence` . Confidence patrí ku konkrétnej zhode; ak ju ukladáte, použite `CHECK` pre rozsah 0-1 a NULL pre neurčenú istotu. Skóre podobnosti 0,95 nie je automaticky 95-percentná pravdepodobnosť správnej identity. FK overuje existenciu cieľa, nie vecnú správnosť párovania. Pokročilý resolver ani číselná confidence nie sú dodatočnou povinnosťou jadra; resolver možno zvoliť ako R1. 

### **Minimálne automatické testy** 

Na oddelených syntetických príkladoch overte neplatný dátum, neplatný JSON oproti chýbajúcej hodnote, neexistujúci dokumentový odkaz a opakované spracovanie záznamu. Overte aj odmietnutie neplatného nenulového FK databázou. Testovacie dáta nevkladajte do zmrazeného korpusu. Vyučujúci musí vedieť zo zdrojového ID dohľadať cieľ aj transformáciu. 

## **7. Finálne jadro: dopyty a indexy** 

Implementujte najmenej šesť dopytov. Pri každom uveďte otázku, tabuľky, parametre, výstupné stĺpce, pravidlo poradia/duplicít a dôvod citlivosti na model alebo index. Vlastné parametre zvoľte podľa dát, zapíšte ich a medzi porovnávanými variantmi nemeňte. 

|**Dopyt**|**Požadovaný výsledok**|
|---|---|
|Q1: Full-text|Vyhľadajte dokumenty alebo chunky. Môžete rozšíriť C1 dopyt`flight`na celý vstup.<br>Výsledok musí obsahovať zdrojové ID.|
|Q2: Fuzzy search|Nájdite podobné mená alebo identifikátory; uveďte vstup, prah/metódu podobnosti,<br>skóre a ID. Podobnosť neprezentujte ako potvrdenie identity.|
|Q3: Relačný 2-hop|V relačne uloženej grafovej vrstve nájdite cesty presne cez dve hrany. Vráťte začiatok,<br>medziuzol, koniec a identity oboch hrán. Určite smer a pravidlo opakovania hrán/uzlov;<br>nezamieňajte cesty s unikátnymi koncami. SQL/PGQ ani Neo4j sa v Z1 nevyžadujú.|
|Q4: Finančná analýza|Implementujte agregáciu finančných záznamov, napríklad podľa meny a obchodníka<br>alebo obdobia. Vráťte aj počet záznamov a odlíšte chýbajúce/neplatné sumy.|
|Q5: Provenance|Zistite konkrétnu vlastnosť spracovania, napríklad opakované spracovanie súborov<br>alebo úspešnosť behov. Pomenujte jednotku počítania; nevydávajte upstream beh za<br>vlastný import.|
|Q6: Vlastná otázka|Zvoľte ďalšiu zmysluplnú analytickú otázku a obhájte ju. Pri dokumentových<br>metadátach môžete využiť JSONB filter a vysvetliť jeho význam.|



JSONB spracovanie z kapitoly 6 musíte vedieť demonštrovať dopytom, napríklad filtrom v Q1 alebo Q6; nemusí to byť siedmy nezávislý dopyt. Malý KG je vhodný na správnosť Q3, nie automaticky na preukázanie výkonu veľkého grafu. 

Navrhnite a implementujte indexy pokrývajúce tieto požiadavky: B-tree, zložený index, GIN pre FTS alebo trigramy a index podľa vlastného rozhodnutia. Pri každom uveďte DDL, dopyt a operátor, poradie kľúčov/opclass, veľkosť a náklady na zápis alebo import. Ak jeden index spĺňa viac uvedených vlastností, výslovne to zdôvodnite; dôležitá je odôvodnená sada pre workload, nie samoúčelné zdvojenie indexu. 

## **8. Finálne jadro: jedno základné porovnanie indexu** 

Vyberte **jeden z dopytov Q1-Q6** a porovnajte ho pred a po vytvorení jedného zdôvodneného pomocného indexu. Použite plný predpísaný vstup príslušných vrstiev, nie malú vzorku C1. Ostatné dopyty musia byť funkčné, ale nemusia mať vlastný benchmark. 

1. Zapíšte očakávanie, presný dopyt a parametre, DDL indexu, verzie PostgreSQL/rozšírení, počty riadkov a základné parametre prostredia. 

2. V oboch variantoch zachovajte rovnaké dáta, SQL a parametre. Meňte iba skúmaný pomocný index. PK, UNIQUE a FK ponechajte aktívne; plán nevynucujte a nevytvárajte umelé kópie dát. 

3. Overte zhodu celého výsledku vrátane identít a počtu výskytov riadkov, nie iba `count(*)` . Použite zoradený export alebo deterministický hash s opísaným formátom. Pri LIMIT/rankingu určite aj poradie pri zhode skóre. 

4. Pre každý variant vykonajte jeden zahrievací beh a **tri merané opakovania** . Rovnakým klientom merajte čas od odoslania po načítanie posledného riadka, bez vykresľovania či zápisu exportu. Nespúšťajte súbežne import. Uveďte všetky časy a medián. 

5. Uložte základný `EXPLAIN` pred/po, definíciu a veľkosť indexu. Stačí pomenovať spôsob prístupu k dátam a prípadné triedenie; detailný rozbor metrík sa nevyžaduje. 

6. Stručne vysvetlite pozorovaný rozdiel, prínos indexu pre vybraný operátor a jeho náklady na zápis a miesto. Z troch opakovaní nerobte všeobecné závery o produkčnom výkone. 

Ide o jednoduché warm porovnanie. Nečistite OS cache a netreba reštartovať databázu. Korektné nezrýchlenie ani Seq Scan nie sú automaticky chyba; nehodnotí sa poradie notebookov podľa rýchlosti. Výsledok patrí do `benchmark.md` a do bodov za dopyty a indexy. 

**Detailný rozbor plánov sa v Z1 nevyžaduje.** Do Z1 nepatria tri výkonové experimenty, desať behov, p95 ani povinné `EXPLAIN (ANALYZE, BUFFERS, SETTINGS)` . Odhady kardinality, loops, buffery a optimalizáciu preberieme na prednáškach/cvičeniach 5-6 a overíme vo výkonovej časti Z2. Archív odovzdaného Z1 sa nemení, databázu a vlastné skripty však ďalej využijete. Nepribúda druhé odovzdanie ani dodatočná bodovaná časť Z1. 

## **9. Jedno povinné rozšírenie za 3 body** 

Vyberte si **jednu** možnosť. Implementáciu, ukážku, overenie a rozhodnutia popíšte v `extension.md` . Nepridávajte všetky možnosti len kvôli počtu technológií. 

### **R1: Resolver nečistých väzieb** 

Implementujte riešenie aspoň jednej situácie: účastník na osobu, zdroj udalosti na dokument alebo správa nevyriešených väzieb. Uchovajte vstup, kandidátov/prijatú zhodu, metódu a stav; odlíšte automatické a manuálne potvrdenie. Na testoch ukážte úspech, neúspech aj nejednoznačnosť a vysvetlite riziko nesprávnej väzby. 

### **R2: Materializovaný pohľad alebo reporting vrstva** 

Implementujte odvodený model pre konkrétnu analytickú otázku, napríklad časovú os alebo agregáciu dokumentov či transakcií. Porovnajte priamy výpočet s odvodeným výsledkom, ukážte obnovu a vysvetlite cenu aktualizácie a zastarané údaje. Obyčajné VIEW a materializovaný výsledok rozlišujte. 

### **R3: Vyhľadávanie ako funkcia aplikácie** 

Vytvorte SQL rozhranie alebo endpoint, ktorý kombinuje full-text, fuzzy match, ranking a filter typu/datasetu/dátumu. Ukážte poradie a relevantné hraničné prípady. Zdôvodnite ranking a rozdiel oproti substringu. Pri rovnakom význame dopytu nesmie samotná zmena indexu meniť správny výsledok; iný slovník, fráza alebo pravidlo rankingu môže meniť otázku a treba to priznať. Frontend nie je potrebný. 

### **R4: Prevádzková analytika provenance** 

Rozšírte analýzu behov a súborov, napríklad o úspešnosť, opakovania alebo chyby validácie. Ukážte dohľadanie konkrétneho problému. Náklady/latenciu vyhodnocujte len tam, kde ich zdroj poskytuje; inak chýbajúce metriky pomenujte. Vysvetlite granularitu záznamu a prečo opakované `file_key` nemusí byť duplicita na odstránenie. 

### **R5: Príprava na priestorovú vrstvu** 

Implementujte tabuľku lokalít a väzbový model pripravený na neskorší import geo dát. Každá väzba má presne jeden subjekt a samostatný voliteľný zdrojový dokument ako provenienciu. Vytvorte príslušné FK a testy integrity. Zdôvodnite budúci priestorový typ, CRS a index oproti samotnému textu alebo dvojici lat/lon. Nepotrebujete vlastné geokódovanie ani celý geo balík; testovacie dáta označte a oddeľte od zdroja. 

## **10. AI report a obhajoba** 

V `ai-report.md` uveďte nástroj/model, dátum a účel použitia, reprezentatívne prompty a relevantné tvrdenia, zoznam prevzatých/opravených častí a vlastné rozhodnutia. Nemusíte odovzdať každý chat, ale musí byť zrejmé, ako ste dôležité odporúčania overili. 

#### Použite krátku tabuľku: 

```
tvrdenie | riziko/predpoklad | test alebo primarny zdroj
pozorovany vysledok | prijatie, oprava alebo odmietnutie
```

Aspoň jedno technické tvrdenie vyvráťte alebo podstatne spresnite. Ak AI nepoužijete, uveďte to a overte tvrdenie, ktoré vám poskytne cvičiaci. Použitie AI ani jeho nepoužitie samo osebe body nemení. 

Na krátkej obhajobe ukážete pôvod a transformáciu vybraného záznamu, vysvetlíte model a indexy, základný spôsob prístupu k dátam a zareagujete na zmenu parametra. Otázka môže zámerne obsahovať nesprávny predpoklad; vašou úlohou nie je súhlasiť s ním. 

## **11. Čo odovzdať do Teams** 

Odovzdajte jeden ZIP so zdrojovým projektom a identifikáciou autora. Ak pracujete v Gite, uveďte v README aj commit odovzdanej verzie; samotný neprístupný odkaz na repozitár nenahrádza spustiteľné odovzdanie. Názov archívu: `Z1_priezvisko_meno.zip` . 

|**Artefakt**|**Obsah**|
|---|---|
|`README.md`|Autor, verzie, konfigurácia, poradie príkazov od downloadu po benchmark, offline<br>opakovanie.|
|Download a manifest|Vlastný download krok a`source-manifest.json`pre celý rozsah.|
|`data-profile.md`|Zistenia zo zdroja a skripty na ich reprodukciu.|
|`data-mapping.md`a model|Source-to-target mapovanie, typy, pravidlá a ER diagram alebo ekvivalent.|
|DDL a importér|`schema.sql`alebo migrácie, vlastná transformácia a evidencia importných behov.|
|Testy a`import-report.md`|Kontroly integrity, účtovanie riadkov, chyby a dôkaz opakovania.|
|`queries.sql`|Q1-Q6, zvolené parametre a vysvetlenie významu.|
|`benchmark.md`a dôkazy|Jeden dopyt pred/po indexe, základné EXPLAIN, tri časy a medián pre každý variant,<br>kontrola výsledku a záver.|
|`ai-report.md`|Tvrdenia AI, ich overenie a vlastné rozhodnutia.|
|`extension.md`a<br>implementácia|Zvolené R1-R5, funkčná ukážka, test a limity.|



Pomenovanie pomocných skriptov môžete prispôsobiť jazyku, ale ich úlohu vysvetlite. Do ZIP nevkladajte dataset, dump, `.env` s heslami, virtuálne prostredie, závislosti ani cache. Zahrňte malé kontrolné výstupy a plány; veľké výsledkové exporty musí vedieť vytvoriť váš skript bez toho, aby ste ich celé odovzdávali. 

C1 odovzdajte v samostatnej položke Teams ako `C1_priezvisko_meno.zip` , s malým adresárom C1 a potrebnými skriptmi aktuálnej verzie toho istého projektu. Jeho rozsah určuje kapitola 4, nie celý zoznam finálnych artefaktov Z1. 

## **12. Bodovanie Z1** 

|**Oblasť**|**Body**|**Čo preukazujete**|
|---|---|---|
|Získanie dát, prostredie a ETL|3|0,5 download/manifest, 0,5 reprodukovateľnosť/offline, 2 vlastný ETL,<br>účtovanie riadkov, validácia a bezpečné opakovanie.|
|Model, mapovanie a integrita|4|2 schéma, typy a mapovanie, 1 validované FK a integritné testy, 1 pôvod dát<br>a evidencia neistoty.|
|Dopyty a indexy|3|1 správne dopyty, 1 zdôvodnené indexy a náklady, 1 základné porovnanie<br>pred/po so zachovaním výsledku.|
|AI audit a obhajoba|2|Overenie odporúčaní a samostatné porozumenie riešeniu.|
|Jedno povinné rozšírenie|3|1 technická správnosť, 1 preukázaný prínos, 1 obhájenie rozhodnutia a<br>limitov.|
|Spolu Z1|15|C1 sa hodnotí samostatne, maximálne za 2 body.|



Čiastočné body sa prideľujú za preukázané oblasti. Chyba v jednej oblasti automaticky nevynuluje ostatné; pri obhajobe sa upravujú body za overované oblasti. Samotný funkčný výstup bez porozumenia nestačí na plný počet. Nehodnotí sa počet riadkov kódu, kozmetika SQL ani to, či váš notebook bol najrýchlejší. 