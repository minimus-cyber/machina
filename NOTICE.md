# NOTICE — Licenze delle risorse esterne

**Leggere prima di ridistribuire qualunque artefatto costruito da questo repo.**

Il codice di Machina è **CC0 1.0** (pubblico dominio). Ma Machina **non
funziona senza dati**, e i dati **non sono di pubblico dominio**.

Questo repo **non ridistribuisce alcun dato**. `scripts/fetch_resources.sh`
scarica ogni risorsa dalla fonte originale. Chi esegue lo script accetta le
licenze di ciascuna fonte.

---

## Le fonti

| Risorsa | Licenza | Ridistribuibile? | Uso commerciale |
|---|---|---|---|
| Whitaker's WORDS (`DICTLINE.GEN`) | pubblico dominio | ✅ | ✅ |
| GF Latin RGL | LGPL | ✅ (LGPL) | ✅ |
| Latin WordNet revision (CIRCSE) | aperta — verificare release | ✅ con attribuzione | ✅ |
| IT-VaLex (CIRCSE) | **GPL-3** | ✅ **ma copyleft** | ✅ (copyleft) |
| UD_Latin-LLCT | CC BY-SA 4.0 | ✅ | ✅ |
| **UD_Latin-Perseus** | **CC BY-NC-SA 2.5** | ✅ | ❌ **NO** |
| **UD_Latin-PROIEL** | **CC BY-NC-SA 3.0** | ✅ | ❌ **NO** |
| **UD_Latin-ITTB** | **CC BY-NC-SA 3.0** | ✅ | ❌ **NO** |
| **UD_Latin-UDante** | **CC BY-NC-SA 3.0** | ✅ | ❌ **NO** |

---

## Le tre conseguenze pratiche

**1. Il copyleft di IT-VaLex (GPL-3).**
Se ridistribuisci la base di conoscenza costruita da IT-VaLex, l'artefatto
derivato è plausibilmente soggetto a GPL-3. Il **codice** di Machina resta CC0
solo perché non incorpora IT-VaLex: lo *legge*.

**2. La clausola NC.**
Quattro dei cinque treebank UD sono **non-commerciali**. Un artefatto costruito
con essi **non può** essere usato commercialmente da nessuno a valle — nemmeno
da chi non sapeva.

*Se il tuo scopo è ricerca e diffusione scientifica, NC non ti ostacola.* Ma se
qualcuno vorrà costruirci sopra un prodotto, si troverà bloccato. Va detto in
anticipo, non scoperto dopo.

**3. Il diritto sui generis sui database (UE).**
Nell'Unione Europea i database godono di una protezione autonoma: l'estrazione
di parti sostanziali è regolata anche quando i singoli fatti non sono
proteggibili. Esiste un'eccezione per la ricerca scientifica (art. 3, Dir.
2019/790), che copre l'uso previsto — ma la ridistribuzione degli estratti è
un'altra questione.

---

## Configurazioni consigliate

**Profilo `clean`** — pubblico dominio effettivo, ridistribuibile senza vincoli:
```
Whitaker's WORDS  +  GF RGL  +  Latin WordNet  +  UD_Latin-LLCT
```
Perdi le valenze di IT-VaLex e i registri NC. Guadagni libertà totale.

**Profilo `research`** — massima copertura, **NC + copyleft**:
```
clean  +  IT-VaLex  +  UD Perseus/PROIEL/ITTB/UDante
```
È il profilo giusto per il tuo scopo dichiarato. Ma **etichettalo**: chi lo usa
deve sapere che eredita NC e GPL-3.

`scripts/fetch_resources.sh --profile clean|research` seleziona il profilo e
scrive `data/LICENSE-PROFILE.txt` con i vincoli ereditati, così l'artefatto
**si autodichiara**.

---

## Non sono un consulente legale

Questa nota è una ricognizione tecnica delle licenze dichiarate dalle fonti, non
un parere legale. Prima di una release pubblica con implicazioni giuridiche,
verifica con chi ha titolo — in particolare l'applicabilità della GPL-3 ai
dataset e la portata del diritto sui generis nella tua giurisdizione.
