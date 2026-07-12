# MACHINA — Motore Deterministico di Ricerca Linguistica

> Documento normativo del progetto. Claude Code deve leggerlo integralmente
> prima di scrivere codice, e rileggerlo a ogni cambio di fase.

---

## 0. Tesi

Machina non predice frasi: **le cerca**. Una frase latina è una *traiettoria
ottimale* in uno spazio di stati linguistici finito e rigorosamente definito.
A parità di stato iniziale, l'output è identico bit per bit.

**Ispirazione, non filiazione.** Il progetto prende da Boris Stilman
(*Linguistic Geometry*) l'idea di rappresentazione gerarchica di uno spazio di
stati, e dai motori scacchistici l'ossatura algoritmica della ricerca. Ma:

- Stilman voleva **sostituire** la ricerca con la costruzione gerarchica. Noi
  facciamo ricerca. Il debito è concettuale, non tecnico: non si dichiari di
  "invertire Stilman" mentre se ne reintroduce l'avversario.
- **Non si forka Stockfish.** Ciò che serve (Iterative Deepening, Branch &
  Bound, Move Ordering, Transposition Table, Aspiration Windows) sono poche
  centinaia di righe di algoritmica generica. Ciò che si erediterebbe (bitboard,
  magic numbers, e soprattutto **NNUE — una rete neurale**) viola i vincoli
  assoluti di questo stesso progetto. Si implementa *ex novo*, ispirandosi
  all'architettura.

---

## 1. I tre modi — partizione completa dei problemi

Machina applica **un solo** algoritmo di ricerca a **tre** classi di problemi.
Non sono tre applicazioni: sono la **partizione completa** dello spazio dei
problemi che un motore di ricerca linguistica può affrontare, ordinati secondo
un'unica variabile — **quanti nodi sono fissati in anticipo**.

| modo | nodi ancorati | agenti | algoritmo | funzione obiettivo |
|---|---|---|---|---|
| **Divinatio** | due (prefisso, suffisso) | 1 | branch & bound best-first | ben definita |
| **Expositio** | uno (tema-radice) | 1 | branch & bound best-first | definibile, manca uno strato |
| **Disputatio** | zero | 2, avversariali | Alpha-Beta | distanza dalla contraddizione |

*Ricostruire, esporre e disputare sono lo stesso problema con condizioni al
contorno diverse.* È questa la tesi architetturale — non un dettaglio
implementativo. Dettaglio completo, motivazioni e costi dichiarati in
`docs/ADR-003.md`.

**Disputatio è self-play.** Machina genera e cerca internamente le mosse di
entrambi i ruoli (Opponens/Respondens) — è un requisito strutturale di
Alpha-Beta, non una scelta. Un interlocutore esterno può solo scegliere fra
mosse legali già generate da Machina, mai scrivere latino libero: farlo
richiederebbe un riconoscitore, cioè il problema che ha già fatto abbandonare
Sermo. Vedi `docs/ADR-004.md` §I.

**Ordine di implementazione: Divinatio → Expositio → Disputatio.**
Divinatio è il modo forte: i vincoli duri collassano lo spazio di ricerca,
la funzione di valutazione già costruita è esattamente quella giusta, il bias
di lunghezza (§6) si dissolve perché la lunghezza della lacuna è nota, ed
esiste un benchmark oggettivo (recupero della lezione vera su un testo
attestato e mutilato ad arte) — l'unico dei tre modi che produce un numero da
mettere in un paper.

---

## 2. Vincoli assoluti

**Vietati:** machine learning, reti neurali, embedding, transformer,
probabilità, euristiche statistiche, generatori pseudocasuali, corpora
frequenziali usati come pesi.

**Consentiti:** logica, algebra, teoria dei grafi, ricerca combinatoria,
programmazione deterministica.

**Corollari operativi non negoziabili:**
- **Solo aritmetica intera** nella funzione di valutazione. Nessun `float`:
  la somma in virgola mobile non è associativa e apre una falla nel determinismo.
- Nessuna iterazione su contenitori non ordinati. Ogni `set` va convertito in
  sequenza ordinata prima di essere percorso.
- Ogni tie-break deve avere una chiave canonica esplicita e totale.
- Nessuna dipendenza da indirizzi di memoria, timestamp, o hash randomizzati.

Due principi che reggono tutto:
1. **Attestazione, non frequenza.** Usare le frequenze di un corpus come pesi
   è statistica → vietato. Usare l'**attestazione** come predicato booleano
   (*questo lemma è attestato in questo slot di questo verbo*) è una
   **relazione logica** → ammesso. Machina legge il corpus come un dizionario,
   non come una distribuzione.
2. **Iponimia, non similarità.** Un filler non attestato è ammesso se è
   **iponimo** di uno attestato. L'iponimia è una relazione d'ordine, non una
   misura di distanza. Nessuna soglia, nessun embedding.

---

## 3. Correzione algoritmica: Branch & Bound per Divinatio/Expositio, Alpha-Beta per Disputatio

Alpha-Beta presuppone due giocatori a somma zero con avversario minimizzante.
La generazione di una frase (Divinatio, Expositio) è **ottimizzazione
mono-agente**. Usare minimax lì è un errore categoriale.

Si adotti, per Divinatio ed Expositio:

| Componente | Ruolo |
|---|---|
| Best-first search (coda di priorità su bound) | esplorazione |
| Branch & Bound con bound ammissibile | pruning |
| Iterative Deepening (profondità = n. di parole) | anytime, move ordering |
| Transposition Table | stati equivalenti visitati una volta |
| Aspiration Window (attorno al best di depth N−1) | restringimento iniziale |
| Move Ordering (transizioni per bound decrescente) | efficienza del pruning |

Il bound deve essere **ammissibile** (mai sottostimare l'ottimo raggiungibile),
altrimenti il pruning perde l'ottimalità e il determinismo diventa vacuo.

⚠ **Aggiornamento (ADR-003).** Questa esclusione di Alpha-Beta vale per
DIVINATIO ed EXPOSITIO, dove l'agente è unico. **DISPUTATIO è l'eccezione
dichiarata**: lì esistono davvero due agenti avversariali a somma zero
(Opponens/Respondens) con ancoraggio esterno oggettivo della valutazione (la
coerenza logica dei *concessa*, verificabile per raggiungibilità nel grafo di
iperonimia del Latin WordNet). Non è un ripensamento della correzione sopra:
è il riconoscimento che il problema non era mai stato l'algoritmo, ma
l'assenza di un vero avversario. Vedi `docs/ADR-003.md`.

---

## 4. La grammatica si autovalida: nessun parser esterno

Non esiste un parser sintattico latino deterministico open source. Quelli
disponibili (LatinCy, Stanza, UDPipe su Perseus/PROIEL/ITTB) sono **neurali**,
dunque vietati. Ma il punto è più profondo: se il Grammar Engine è generativo e
completo, **la grammatica che genera è la stessa che valida**. Un parser esterno
sarebbe ridondante e introdurrebbe una seconda fonte di verità.

Esistono e vanno usati solo analizzatori **morfologici** deterministici, come
riferimento e come oracolo di test:
- **LEMLAT 3** — analizzatore morfologico basato su dizionario
- **Collatinus** — GPL, con lessico
- **Whitaker's Words** — pubblico dominio

Vanno usati per *verificare* le forme prodotte, non per produrle.

Questo vincolo vale anche per DISPUTATIO (§1): non serve un parser per
riconoscere latino libero, perché l'Opponens genera proposizioni con la stessa
grammatica generativa, non le riceve da un input arbitrario esterno.

---

## 5. Risorse esterne: cosa esiste davvero

Verificato scaricando le fonti, non citandole da un paper. Stack completo e
numeri misurati in `docs/ADR-001.md` e `docs/ADR-002.md`.

| Risorsa | Licenza | Cosa dà | Blocco risolto |
|---|---|---|---|
| **Whitaker's WORDS** (`DICTLINE.GEN`) | pubblico dominio | 39.338 entrate, classe flessiva esplicita | coniugazione: 39%→3% indecidibile |
| **Latin WordNet revision** (CIRCSE) | aperta | 13.868 relazioni `wn:hypernym` | tassonomia — è la sorgente per Disputatio (§1) |
| **IT-VaLex** (CIRCSE) | GPL-3 | 353.036 token, 78.711 argomenti verbali con filler | valenza e restrizioni selettive |
| **GF Latin RGL / DictLat** | LGPL | 36.613 entrate | lessico, oracolo di validazione morfologica |
| **UD Latin** ×5 (Perseus, PROIEL, ITTB, UDante, LLCT) | ⚠ 4/5 CC BY-NC-SA | 984k token, 5 registri | registro; incrocio fra treebank per ripulire il rumore |

**Decisione presa (ADR-001 §3):** GF **non** è il core — linearizza, non cerca,
e non ha funzione di valutazione. Fornisce lessico e paradigmi; il motore
resta autonomo.

**Non esiste:** un lessico comeniano strutturato machine-readable. Vedi §6.

---

## 6. FASE 0 — Costruzione filologica della base di conoscenza

Con lo stack di §5, la Fase 0 si riduce a **curare i frame** (rumore in
IT-VaLex, mitigabile per incrocio fra treebank) e **colmare le lacune di LWN**
(~15-20% di lemmi comeniani senza mappatura tassonomica) — entrambi lavori
finiti, non annotazione da zero.

Deliverable: `data/lexicon.json` + `data/taxonomy.json` (costruiti da
`scripts/fetch_resources.sh` + build), più il **golden set**: 100 frasi
corrette + 100 scorrette, giudicate dal filologo. **È l'unica cosa non
automatizzabile del progetto.**

**Memoria di apprendimento.** Questi stessi file possono crescere nel tempo
come accumulo monotono di fatti logici (nuove attestazioni, nuove iponimie,
nuovi esiti verificati) con provenienza dichiarata — mai come pesi statistici
aggiustati da un segnale di rinforzo. Se non si può mostrare con `git diff`,
non è la memoria ammessa da questo progetto. Vedi `docs/ADR-004.md` §II.

---

## 7. Funzione di valutazione — e il suo difetto noto

```
GRAM  è un FILTRO, non un addendo.
      Una violazione non abbassa il punteggio: cancella lo stato.

Score = β·SEM + γ·SYN + δ·TAX + ε·ORD        [interi]
```

- **SEM** — aderenza del filler alla restrizione selettiva dello slot, come
  *scarto tassonomico* (`gap`): quanti gradini separano il lemma dal taxon
  richiesto.
- **TAX** — coerenza fra i partecipanti: profondità del minimo antenato comune.
- **SYN** — continuità sintagmatica: adiacenza modificatore/testa,
  preposizione/reggente.
- **ORD** — "eleganza strutturale" definita *operativamente*: conformità ai
  parametri d'ordine non marcati del latino (verbo finale; ACT precede PAT;
  preposizione adiacente al reggente). Parametri **dichiarati, ispezionabili e
  modificabili**, non un giudizio estetico.

Questi pesi sono il primo caso reale del **registro unico di parametri
etico-epistemologici** richiesto da `docs/ADR-004.md` §III: dichiarati non
basta, ognuno deve avere un test di falsificabilità (es. cambiare i pesi non
deve mai rompere l'ammissibilità del bound, §3).

### ⚠ Difetto A — bias di lunghezza (il più grave, aperto)

La formula è **monotona crescente nella lunghezza**: ogni costituente aggiunge
punti, nulla lo penalizza. `go depth N` satura sempre: il motore produce la
frase **più lunga ammissibile**, non la migliore. Osservato:
`primus agens primam formam corpori applicat` — l'aggettivo c'è solo perché
frutta punti. **Da correggere prima del primo tag pubblico.**

Rimedi da valutare in Fase 4: normalizzazione per lunghezza (arrotondamento
canonico, o score ×1000 per restare interi); costo fisso per costituente
opzionale; separare adeguatezza da ornamento.

**In DIVINATIO (§1) questo difetto non si presenta**: la lunghezza della
lacuna è nota (misurabile su pietra/papiro), diventa vincolo dato, non
variabile da massimizzare.

### Difetti B, C — aperti, dichiarati

- **B — Frame rumorosi.** IT-VaLex è indotto da parse: soggetti in ablativo,
  soggetti in accusativo, tripli accusativi sopravvivono come artefatti.
  Mitigabile per incrocio fra treebank indipendenti (attestazione in ≥2
  treebank, non soglia di frequenza — resta un filtro logico su insiemi).
- **C — Golden set assente.** Vedi §6.

---

## 8. Architettura

```
      stato semantico
             │
     Knowledge Layer          ← valenze, restrizioni selettive, tassonomia
             │
     Grammar Engine           ← decide il LEGALE (morfologia, accordo, valenza)
             │
     Search Engine            ← decide il PREFERIBILE (best-first + B&B, o
             │                   Alpha-Beta per Disputatio — vedi §1, §3)
      Evaluation              ← interi puri
             │
   frase latina + traccia completa
```

La grammatica **si autovalida**: la stessa grammatica che genera è quella che
verifica. Nessun parser esterno (§4).

**Sul "tensore di rango 4".** `R(i,j,k,l)` con relazioni logiche sparse è, in
matematica, un **grafo di conoscenza etichettato**. Si implementi come
grafo/relazione sparsa e si dichiari tale.

---

## 9. Fasi

| Fase | Contenuto | Uscita |
|---|---|---|
| **0** | Base di conoscenza filologica | `lexicon.json`, `taxonomy.json`, golden set |
| **1** | Grammar Engine (morfologia + accordo + valenza) | forme verificate contro LEMLAT/Whitaker |
| **2** | Search Engine (best-first, B&B, ID, TT) | ottimalità dimostrata su casi piccoli |
| **3** | Evaluation + correzione del bias di lunghezza (§7) | ablation study dei pesi |
| **4** | CLI + Zero-Entropy Test | fingerprint SHA-256 riproducibile |

Dopo la Fase 4, i tre modi (§1): **Divinatio → Expositio → Disputatio**, in
quest'ordine, ciascuno come fase a sé con deliverable proprio (Expositio
richiede in più la grammatica del discorso dell'*articulus* scolastico;
Disputatio richiede il checker di coerenza sillogistica — entrambi dettagliati
in `docs/ADR-003.md`).

Procedere **in sequenza**. Ogni fase produce: codice compilabile, test
automatici, benchmark, documentazione.

---

## 10. Zero-Entropy Test — specifica

Non basta "eseguire due volte e confrontare". Il test deve:

1. eseguire N≥200 volte in-process → output identici;
2. eseguire in **processi separati con seed di hash diversi** (in C++: ASLR
   attivo, allocatori diversi, `-O0` e `-O3`) → output identici;
3. confrontare un **fingerprint SHA-256** che includa non solo la frase, ma
   **anche le statistiche di ricerca** (nodi esplorati, nodi potati, hit di TT).
   Se una frase è identica ma il conteggio dei nodi no, c'è entropia nascosta
   nella ricerca: il test deve rilevarla.

Il prototipo Python allegato supera già questo test.

---

## 11. CLI

```
setstate <lemmi|taxa>   go depth N   generate   status
trace                   explain      export-tree
```

Ogni frase deve uscire con: albero sintattico, percorso di ricerca, punteggio
scomposto per componente, motivazione delle scelte, nodi esplorati, nodi potati.

Per DIVINATIO (§1), nuova firma quando implementata (non prima della Fase
dedicata):
```
reconstruct(prefix_tokens, suffix_tokens, gap_len_chars) -> lectio + traccia
```
`gap_len_chars` è un **vincolo duro** sul bound, non un premio.

---

## 12. Linguaggio

C++20, struttura modulare, niente dipendenze non dichiarate.
Il prototipo Python in `prototype/` è la **specifica eseguibile**: il C++ deve
riprodurne l'output esattamente sugli stessi stati iniziali.

---

## 13. Metodo di lavoro (non negoziabile)

- Un test che **conta le righe** non prova nulla. Un test che verifica una
  **proprietà logica** prova qualcosa (es. antisimmetria della sussunzione,
  invarianza del fingerprint sotto `PYTHONHASHSEED` randomizzato, rifiuto di
  indovinare su verbi indecidibili).
- Quando qualcosa fallisce, **non aggiustarlo per farlo funzionare**: mostrare
  lo scarto fra atteso e osservato. Ogni difetto dei dati trovato finora
  (§5-§7) è emerso così.
- L'onestà sui limiti è parte dell'argomento scientifico, non un difetto da
  nascondere nel README.
- **La trasparenza è un requisito testabile, non solo un'intenzione.** Ogni
  funzione che produce un output linguistico (`generate`, e in futuro
  `reconstruct` per Divinatio, `dispute` per Disputatio) **deve** restituire
  una traccia completa: nessun percorso di codice può produrre una frase, una
  lectio o una mossa di disputa senza la traccia che la accompagna. Un test
  dedicato (accanto allo Zero-Entropy Test, §10) deve verificarlo: non basta
  che l'output sia deterministico, deve essere sempre ricostruibile *perché*
  è quello. "La frase non è il prodotto. La traccia lo è" non è uno slogan
  del README: è un vincolo di codice.
