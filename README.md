# Machina

**Un motore deterministico di ricerca linguistica per il latino.**

Machina non predice frasi. Le **cerca**.

Una frase latina è trattata come una *traiettoria ottimale* in uno spazio di
stati finito e rigorosamente definito: date le valenze di un verbo, le
restrizioni selettive sui suoi argomenti e le regole di accordo, il motore
esplora lo spazio delle realizzazioni ammissibili e restituisce quella che
massimizza una funzione obiettivo dichiarata.

A parità di stato iniziale, l'output è **identico bit per bit**.

---

## Cosa Machina non è

Nessuna rete neurale. Nessuna probabilità. Nessun embedding. Nessun generatore
pseudocasuale. Nessuna euristica statistica.

Solo: logica, algebra, teoria dei grafi, ricerca combinatoria.

Questo non è un vezzo. È il punto: ogni frase prodotta è accompagnata
dall'albero sintattico, dal percorso di ricerca, dal punteggio scomposto per
componente, dai nodi esplorati e dai nodi potati. **Ogni decisione è
ispezionabile e riproducibile.**

---

## Ispirazione, e un debito dichiarato con onestà

Il progetto nasce riflettendo sulla *Linguistic Geometry* di Boris Stilman e
sull'architettura dei motori scacchistici.

Va detto con precisione: Stilman voleva **sostituire** la ricerca con la
costruzione gerarchica. Machina fa ricerca. Il debito è concettuale — l'idea di
uno spazio di stati gerarchico e di traiettorie ammissibili — non tecnico.

E l'algoritmo **non è (sempre) Alpha-Beta**. Alpha-Beta presuppone un avversario
minimizzante; generare o ricostruire una frase è ottimizzazione *mono-agente*.
Si usa **branch & bound best-first**, conservando dell'ossatura scacchistica ciò
che è realmente trasferibile: iterative deepening, move ordering, transposition
table, aspiration windows. L'eccezione è dichiarata: vedi sotto.

---

## I tre modi — una partizione, non una lista di funzionalità

Machina applica **un solo** algoritmo di ricerca a **tre** classi di problemi,
ordinate secondo un'unica variabile: quanti nodi dello spazio di stati sono
fissati in anticipo. Non sono tre funzionalità — sono la **partizione completa**
delle condizioni al contorno che un motore di ricerca linguistica può ricevere.

| modo | nodi ancorati | agenti | algoritmo | obiettivo |
|---|---|---|---|---|
| **Divinatio** — ricostruzione filologica | due (prefisso, suffisso) | 1 | branch & bound best-first | ben definito |
| **Expositio** — sviluppo argomentativo | uno (tema-radice) | 1 | branch & bound best-first | definibile, manca uno strato |
| **Disputatio** — disputa scolastica | zero | 2, avversariali | Alpha-Beta | distanza dalla contraddizione |

**Divinatio** è il modo di punta, e il primo a essere implementato: dato un
testo mutilo, cerca la lezione che salda i nodi validi adiacenti. Qui il bias
di lunghezza (vedi *Limiti noti*) si dissolve — in epigrafia e papirologia
l'ampiezza della lacuna è nota, quindi diventa un vincolo dato, non una
variabile da massimizzare — ed esiste un benchmark oggettivo: cancellare
artificialmente porzioni di un testo attestato e misurare quante volte Machina
recupera la lezione vera.

**Il confronto che vale è con Ithaca** (DeepMind), che restituisce iscrizioni
greche per via neurale. Contro Ithaca **non serve vincere in accuratezza**: si
vince in ispezionabilità, e per costruzione — un sistema probabilistico che non
sa dire perché, contro uno deterministico che espone l'intera catena
inferenziale.

**Disputatio** è l'unico modo genuinamente avversariale, e l'unico dove
Alpha-Beta è l'algoritmo corretto (non un ripensamento della scelta sopra: è il
riconoscimento che il problema non era mai l'algoritmo, ma l'assenza di un vero
avversario). Formalizza la *disputatio* scolastica medievale — Opponens contro
Respondens, con vittoria quando il Respondens è costretto a contraddirsi —
sfruttando il grafo di iperonimia del Latin WordNet come dominio sillogistico
già pronto. Dettagli, costi dichiarati e le decisioni conseguenti (chi genera le
mosse, perché non un dialogo libero) in `docs/ADR-003.md` e `docs/ADR-004.md`.

Ordine di implementazione: **Divinatio → Expositio → Disputatio**.

---

## Architettura

```
      stato semantico
             │
     Knowledge Layer          ← valenze, restrizioni selettive, tassonomia
             │
     Grammar Engine           ← decide il LEGALE (morfologia, accordo, valenza)
             │
     Search Engine            ← decide il PREFERIBILE (best-first + B&B, o
             │                   Alpha-Beta per Disputatio)
      Evaluation              ← interi puri (mai float: la somma float non è associativa)
             │
   frase latina + traccia completa
```

La grammatica **si autovalida**: la stessa grammatica che genera è quella che
verifica. Nessun parser esterno — e nemmeno sarebbe possibile, dato che i parser
sintattici latini disponibili sono tutti neurali.

---

## Le risorse (nessuna è ridistribuita: si scaricano)

| Risorsa | Licenza | Ruolo |
|---|---|---|
| [Whitaker's WORDS](https://github.com/mk270/whitakers-words) | pubblico dominio | classe flessiva esplicita, 4 temi principali |
| [Latin WordNet revision](https://github.com/CIRCSE/latinWordnet-revision) (CIRCSE) | aperta | **13.868 relazioni di iperonimia** → la tassonomia, e il dominio sillogistico di Disputatio |
| [IT-VaLex](https://github.com/CIRCSE/ITVALEX) (CIRCSE) | GPL-3 | valenze + filler attestati (353k token) |
| [GF Latin RGL](https://github.com/GrammaticalFramework/gf-rgl) | LGPL | lessico, oracolo di validazione |
| [UD Latin](https://github.com/UniversalDependencies) ×5 | **⚠ vedi NOTICE** | 984k token, 5 registri |

**Non sono citate da un paper: sono state scaricate, parsate e misurate.**
Vedi `docs/ADR-001.md` e `docs/ADR-002.md` per i numeri e per due difetti dei
dati che nessuna documentazione segnala.

---

## Due principi che tengono in piedi il determinismo

**1. Attestazione, non frequenza.**
Usare le frequenze di un corpus come pesi sarebbe statistica → vietato.
Usare l'**attestazione** come predicato booleano (*questo lemma è attestato in
questo slot di questo verbo*) è una **relazione logica** → ammesso.
Machina legge il corpus **come un dizionario, non come una distribuzione**.

**2. Iponimia, non similarità.**
Un filler non attestato è ammesso se è **iponimo** di uno attestato. L'iponimia
è una relazione d'ordine, non una misura di distanza. Nessuna soglia, nessun
embedding.

---

## Limiti noti, dichiarati

- **Bias di lunghezza.** La funzione di valutazione è monotona crescente nel
  numero di costituenti: `go depth N` satura sempre. Il motore produce la frase
  *più lunga ammissibile*, non la migliore. Da correggere prima del primo tag
  pubblico. **Non si presenta in Divinatio** (vedi sopra).
- **Frame rumorosi.** IT-VaLex è indotto automaticamente da parse: sopravvivono
  artefatti (soggetti in ablativo, tripli accusativi). Mitigabile per incrocio
  fra treebank indipendenti.
- **16 verbi irregolari** (composti di *esse*, deponenti anomali) richiedono
  tabelle esplicite.
- **"Eleganza strutturale"** è definita *operativamente* come conformità ai
  parametri d'ordine non marcati del latino (verbo finale, ACT precede PAT).
  Sono parametri **dichiarati e modificabili**, non un giudizio estetico.
  Determinismo e arbitrarietà sono compatibili: il primo non redime la seconda.
  Ciò che redime l'arbitrarietà è dichiararla — vedi `docs/ADR-004.md` per come
  questo principio viene formalizzato in un registro unico di parametri,
  vincolato dalla falsificabilità.
- **Golden set assente.** Servono 100 frasi corrette + 100 scorrette, giudicate
  dal filologo. È l'unica cosa non automatizzabile del progetto.

L'onestà su questi limiti è parte dell'argomento scientifico, non qualcosa da
nascondere.

---

## Uso

```bash
git clone https://github.com/<utente>/machina
cd machina
./scripts/fetch_resources.sh      # scarica le fonti (non ridistribuite)
python -m machina.build            # costruisce la base di conoscenza
python -m machina.cli generate --verb amo --num sg
```

## Licenza

**Codice: CC0 1.0 — pubblico dominio.** Usalo, forkalo, non citarmi se non vuoi.

**Dati: NON ridistribuiti.** Ognuno resta sotto la propria licenza. Leggi
[`NOTICE.md`](NOTICE.md) **prima** di ridistribuire qualunque artefatto
costruito.
