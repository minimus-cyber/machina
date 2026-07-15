"""
MACHINA / REAL — il motore sulle risorse vere.

  valenza + restrizioni selettive : ITVALEX  (Index Thomisticus Treebank, GPL-3)
  paradigmi morfologici           : GF DictLat (RGL, LGPL; da Whitaker's WORDS)

Le restrizioni selettive NON sono una tassonomia scritta a mano: sono
l'insieme dei filler ATTESTATI per quello slot di quel verbo. Attestazione =
predicato booleano = relazione logica. Nessuna frequenza, nessun peso appreso.

Ricerca sull'ordine: best-first + Branch & Bound con bound ammissibile,
Transposition Table, Iterative Deepening + Aspiration Window (CLAUDE.md §3).
Non piu' enumerazione a forza bruta delle permutazioni: quella trovava
comunque l'ottimo (per costruzione, su combo piccole), ma non dimostrava
ne' testava l'architettura di ricerca richiesta dal progetto.
"""
from __future__ import annotations
import json, re, itertools, heapq, sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Union

# ==========================================================================
# 0. Percorsi (relativi alla radice del repo, non alla sandbox originale)
# ==========================================================================
ROOT = Path(__file__).resolve().parent.parent
GF = ROOT / "data" / "src" / "gf-rgl" / "src" / "latin" / "DictLat.gf"
DATA_REAL = ROOT / "data" / "data_real.json"

# ==========================================================================
# 1. Ricostruzione del lessico GF (con le insidie corrette)
# ==========================================================================
def load_gf():
    """Cattura anche mkV2/mkV3 (i transitivi!) e preferisce le entrate
    con piu' forme, da cui la coniugazione e' ricavabile."""
    N, A, V = {}, {}, {}
    reN = re.compile(r'^\s*(\w+?)_(?:F_N|M_N|N_N|N)\d*\s*=\s*mkN\s+(.*?)\s*;')
    reA = re.compile(r'^\s*(\w+?)_A\d*\s*=\s*mkA\s+(.*?)\s*;')
    reV = re.compile(r'^\s*(\w+?)_V\d?\d*\s*=\s*(?:mkV[23]?\s*\(\s*)?mkV\s+(.*)')
    with open(GF, encoding="utf-8", errors="replace") as f:
        for line in f:
            if (m := reN.match(line)):
                f_ = re.findall(r'"([^"]+)"', m.group(2))
                g = ("masculine" in m.group(2) and "m") or ("feminine" in m.group(2) and "f") \
                    or ("neuter" in m.group(2) and "n") or ""
                if f_ and (m.group(1) not in N or len(f_) > len(N[m.group(1)]["f"])):
                    N[m.group(1)] = {"f": f_, "g": g}
            elif (m := reA.match(line)):
                f_ = re.findall(r'"([^"]+)"', m.group(2))
                if f_ and (m.group(1) not in A or len(f_) > len(A[m.group(1)]["f"])):
                    A[m.group(1)] = {"f": f_}
            elif (m := reV.match(line)):
                f_ = re.findall(r'"([^"]+)"', m.group(2))
                # PREFERENZA per l'entrata con piu' forme: risolve lego=legare vs legere
                if f_ and (m.group(1) not in V or len(f_) > len(V[m.group(1)]["f"])):
                    V[m.group(1)] = {"f": f_}
    return N, A, V

GN, GA, GV = load_gf()

# ==========================================================================
# 2. Morfologia: paradigmi intelligenti (come ParadigmsLat), deterministici
# ==========================================================================
DECL = {
 "1":  dict(nom_sg="a",  gen_sg="ae", acc_sg="am", abl_sg="a",  dat_sg="ae",
            nom_pl="ae", acc_pl="as", abl_pl="is"),
 "2":  dict(nom_sg=None, gen_sg="i",  acc_sg="um", abl_sg="o",  dat_sg="o",
            nom_pl="i",  acc_pl="os", abl_pl="is"),
 "2n": dict(nom_sg="um", gen_sg="i",  acc_sg="um", abl_sg="o",  dat_sg="o",
            nom_pl="a",  acc_pl="a",  abl_pl="is"),
 "3":  dict(nom_sg=None, gen_sg="is", acc_sg="em", abl_sg="e",  dat_sg="i",
            nom_pl="es", acc_pl="es", abl_pl="ibus"),
}

class Undecidable(Exception): pass

def noun_paradigm(lemma: str, e: dict):
    """Ritorna (stem, decl, gender) o solleva Undecidable."""
    f, g = e["f"], e["g"]
    nom = f[0]
    if len(f) >= 2:                                  # nom + gen: caso sicuro
        gen = f[1]
        if gen.endswith("ae"): return gen[:-2], "1", g or "f"
        if gen.endswith("is"): return gen[:-2], "3", g or "m"
        if gen.endswith("i"):
            return gen[:-1], ("2n" if nom.endswith("um") else "2"), g or ("n" if nom.endswith("um") else "m")
        raise Undecidable(f"genitivo non riconosciuto: {lemma} {gen}")
    # una sola forma: paradigma intelligente sul nominativo
    if nom.endswith("a"):  return nom[:-1], "1",  g or "f"
    if nom.endswith("um"): return nom[:-2], "2n", "n"
    if nom.endswith("us"): return nom[:-2], "2",  g or "m"
    raise Undecidable(f"declinazione non ricavabile dal solo nominativo: {lemma} ({nom})")

def decline(lemma, e, case, num):
    stem, d, g = noun_paradigm(lemma, e)
    key = f"{case}_{num}"
    if key == "nom_sg" and DECL[d]["nom_sg"] is None:
        return e["f"][0]
    suf = DECL[d].get(key)
    if suf is None: raise Undecidable(f"{lemma} {key}")
    return stem + suf

ADJ = {"m": {"nom_sg":"us","acc_sg":"um","abl_sg":"o","nom_pl":"i","acc_pl":"os","abl_pl":"is"},
       "f": {"nom_sg":"a", "acc_sg":"am","abl_sg":"a","nom_pl":"ae","acc_pl":"as","abl_pl":"is"},
       "n": {"nom_sg":"um","acc_sg":"um","abl_sg":"o","nom_pl":"a", "acc_pl":"a", "abl_pl":"is"}}

def decline_adj(lemma, e, gender, case, num):
    f = e["f"]
    if len(f) < 3: raise Undecidable(f"aggettivo non 1-2: {lemma}")
    base = f[0]
    if not base.endswith("us"): raise Undecidable(f"agg. non regolare: {lemma}")
    stem = base[:-2]
    if (gender, case, num) == ("m", "nom", "sg"): return base
    return stem + ADJ[gender][f"{case}_{num}"]

CONJ = {"1": dict(sg="at", pl="ant"), "2": dict(sg="et", pl="ent"),
        "3": dict(sg="it", pl="unt"), "4": dict(sg="it", pl="iunt")}

def verb_conj(lemma, e):
    """Coniugazione ricavabile SOLO da 1sg. Dall'infinito senza macron
    -ere e' ambiguo (2a vs 3a): si solleva Undecidable, non si tira a indovinare."""
    f = e["f"]
    inf = f[0]
    if inf.endswith("are"): return inf[:-3], "1"
    if inf.endswith("ire"): return inf[:-3], "4"
    if len(f) >= 2:
        p1 = f[1]
        if p1.endswith("eo"): return p1[:-2], "2"       # video -> vid-
        if p1.endswith("io"): return p1[:-2], "4"
        if p1.endswith("o"):  return p1[:-1], "3"       # lego  -> leg-
    raise Undecidable(f"coniugazione non ricavabile (manca 1sg, -ere ambiguo): {lemma}")

def conjugate(lemma, e, num):
    stem, c = verb_conj(lemma, e)
    return stem + CONJ[c][num]

def infinitive(lemma, e):
    """L'infinito e' gia' la prima forma del paradigma GF (es. 'amare',
    'legere'): non va derivato, e' dato."""
    return e["f"][0]

# ==========================================================================
# 2bis. Verbi servili/fraseologici — tabella esplicita e dichiarata
#
# Il predicato puo' essere composto: modale/fraseologico coniugato + infinito
# del verbo lessicale (es. "debet amare"). Il motore si rifiuta di indovinare
# anche qui: solo i lemmi qui dichiarati sono ammessi come testa di un
# predicato composto, e solo con la coniugazione qui specificata a mano.
#
#   'debeo'  — regolare (2a coniug.), ma GF DictLat non ne da' la 1sg:
#              risulterebbe UNDECIDABLE per la via normale (verb_conj).
#   ESCLUSI dichiaratamente, non per dimenticanza:
#   'possum' — assente da GF DictLat (irregolare, composto pot+esse).
#   'volo'   — collide nei dati GF con 'volare' (1a coniug., "volare"):
#              stessa insidia lego/lego2 di ADR-001 §2a. Richiede una voce
#              separata prima di poter essere usato; non si indovina quale
#              delle due letture sia quella intesa.
# ==========================================================================
PHRASAL_STEMS = {"debeo": "deb"}
PHRASAL_CONJ  = {"debeo": "2"}
PHRASAL_VERBS = tuple(sorted(PHRASAL_CONJ))

def phrasal_conjugate(lemma: str, num: str) -> str:
    return PHRASAL_STEMS[lemma] + CONJ[PHRASAL_CONJ[lemma]][num]

# ==========================================================================
# 3. Base di conoscenza reale
# ==========================================================================
D = json.load(open(DATA_REAL))

def canonical(frame):
    """Filtra i frame indotti automaticamente: scarta gli artefatti di parsing."""
    rels = [s[0] for s in frame]
    if rels.count("Sb") > 1 or len(frame) > 3: return False
    if rels.count("Obj") > 2: return False
    if any(s[1] == "" and s[0] != "Sb" for s in frame): return False
    return "Sb" in rels

CASEMAP = {"nom": "nom", "acc": "acc", "abl": "abl", "dat": "dat", "gen": "gen"}

# ==========================================================================
# 4. Costituenti, predicato e valutazione (interi puri)
# ==========================================================================
@dataclass(frozen=True)
class C:
    rel: str; noun: str; adj: Optional[str]; case: str; num: str
    prep: str; words: Tuple[str, ...]

@dataclass(frozen=True)
class Pred:
    """Il predicato: un verbo finito da solo, oppure — se sia il modale sia
    il verbo lessicale sono fra i semi forniti — la composizione dichiarata
    in PHRASAL_VERBS. L'ordine interno (modale poi infinito) e' fisso, non
    fa parte della ricerca sull'ordine: il predicato resta un solo elemento
    nella sequenza, come nella versione a verbo singolo."""
    words: Tuple[str, ...]
    lemmas: Tuple[str, ...]   # ultimo elemento = verbo che governa il frame

Item = Union[C, Pred]

W_SLOT, W_ADJ = 40, 8
W_VFIN, W_SBOBJ, W_SB1ST = 15, 10, 8
MAXORD = W_VFIN + W_SBOBJ + W_SB1ST

W_SEED = 25   # bonus per seme distinto incorporato nella frase — dichiarato,
              # non un effetto collaterale del bias di lunghezza (CLAUDE.md §7):
              # e' il termine esplicito che fa preferire "piu' semi usati",
              # non solo "piu' parole"

def build(rel, case, prep, noun, adj, num):
    if noun not in GN: return None
    try:
        stem, d, g = noun_paradigm(noun, GN[noun])
        head = decline(noun, GN[noun], CASEMAP[case], num)
        w = [prep] if prep else []
        if adj:
            af = decline_adj(adj, GA[adj], g, CASEMAP[case], num)
            w += [af, head]
        else:
            w += [head]
    except (Undecidable, KeyError):
        return None
    return C(rel, noun, adj, case, num, prep, tuple(w))

def score_plan(combo: List[C], pred: Pred, seeds: frozenset) -> int:
    """Componente indipendente dall'ordine: valenza/accordo (come prima) piu'
    il bonus esplicito di copertura dei semi (W_SEED, dichiarato sopra)."""
    base = sum(W_SLOT + (W_ADJ if c.adj else 0) for c in combo)
    used = set(pred.lemmas) | {c.noun for c in combo} | {c.adj for c in combo if c.adj}
    return base + W_SEED * len(used & seeds)

def order_score(items: List[Item], vi: int) -> int:
    """Componente dipendente dall'ordine ('eleganza strutturale', CLAUDE.md §7).
    vi = posizione del predicato (Pred) nella sequenza."""
    s = 0
    n = len(items)
    if vi == n - 1: s += W_VFIN
    pos = {c.rel: i for i, c in enumerate(items) if isinstance(c, C)}
    if "Sb" in pos and "Obj" in pos and pos["Sb"] < pos["Obj"]: s += W_SBOBJ
    if pos.get("Sb") == 0: s += W_SB1ST
    return s

# ==========================================================================
# 5. Statistiche di ricerca (per la traccia e per il fingerprint — CLAUDE.md §10/§13)
# ==========================================================================
@dataclass
class Stats:
    nodes: int = 0
    plans: int = 0
    pruned_bound: int = 0
    pruned_grammar: int = 0
    tt_hits: int = 0

# ==========================================================================
# 6. Predicati e costituenti candidati a partire dai SEMI (non piu' un solo
#    verbo): universo chiuso, come nel prototipo originale (SemanticState) —
#    i filler ammessi sono solo i lemmi forniti dall'utente, non l'intero
#    corpus.
# ==========================================================================
def build_predicates(seed_verbs: Tuple[str, ...], num: str) -> List[Pred]:
    """Un Pred per ogni verbo seme risolvibile da solo, piu' un Pred per ogni
    composizione modale+infinito quando ENTRAMBI i lemmi sono fra i semi
    (il modale non entra mai di nascosto)."""
    preds: List[Pred] = []
    seed_set = set(seed_verbs)

    for v in sorted(seed_set):
        if v not in D["verbs"]:
            continue
        try:
            vw = conjugate(v, GV[v], num)
            preds.append(Pred((vw,), (v,)))
        except (Undecidable, KeyError):
            pass   # non utilizzabile da solo — puo' comunque comparire come infinito sotto un modale

    for modal in sorted(seed_set & set(PHRASAL_VERBS)):
        mconj = phrasal_conjugate(modal, num)
        for v in sorted(seed_set - {modal}):
            if v not in D["verbs"] or v in PHRASAL_VERBS:
                continue
            try:
                inf = infinitive(v, GV[v])
            except KeyError:
                continue
            preds.append(Pred((mconj, inf), (modal, v)))

    return preds

def enumerate_combos_seeded(frame, fillers: Dict[str, List[str]],
                             seed_nouns: Tuple[str, ...], seed_adjs: Tuple[str, ...],
                             num: str, budget: int, stats: Stats):
    """Come la vecchia enumerate_combos, ma i filler ammessi per ogni slot
    sono SOLO i nomi/aggettivi forniti come semi (intersecati con
    l'attestazione IT-VaLex dello slot), non l'intero corpus. `budget` e' il
    numero di parole disponibili per i costituenti (max_words meno le parole
    gia' impegnate dal predicato)."""
    slots = [tuple(s) for s in frame]
    per = []
    for rel, case, prep in slots:
        key = "|".join((rel, case, prep))
        attested = set(fillers.get(key, []))
        cands = [n for n in seed_nouns if n in attested]
        opts = []
        for nl in sorted(cands):
            for al in (None,) + tuple(sorted(a for a in seed_adjs)):
                c = build(rel, case, prep, nl, al, num)
                if c:
                    opts.append(c)
                else:
                    stats.pruned_grammar += 1
        if not opts:
            return
        per.append(opts)

    for combo in itertools.product(*per):
        if len({c.noun for c in combo}) != len(combo):
            stats.pruned_grammar += 1
            continue
        nw = sum(len(c.words) for c in combo)
        if nw > budget:
            stats.pruned_bound += 1
            continue
        stats.plans += 1
        yield list(combo)

# ==========================================================================
# 7. Ricerca sull'ordine: best-first + Branch & Bound + Transposition Table
# ==========================================================================
def _admissible_bound(new_emitted: Tuple[int, ...], items: List[Item], base: int) -> int:
    """Bound ottimistico dopo aver fissato le posizioni in new_emitted.
    Deve non sottostimare mai l'ottimo raggiungibile (CLAUDE.md §3)."""
    b = base + MAXORD
    n = len(items)

    verb_k = next((k for k, i in enumerate(new_emitted) if not isinstance(items[i], C)), None)
    if verb_k is not None and len(new_emitted) < n:
        b -= W_VFIN                      # il verbo non e' l'ultimo emesso: perso per sempre

    if new_emitted:
        first = items[new_emitted[0]]
        if not (isinstance(first, C) and first.rel == "Sb"):
            b -= W_SB1ST                 # la posizione 0 e' fissata e non e' Sb

    sb_k = next((k for k, i in enumerate(new_emitted)
                 if isinstance(items[i], C) and items[i].rel == "Sb"), None)
    obj_k = next((k for k, i in enumerate(new_emitted)
                  if isinstance(items[i], C) and items[i].rel == "Obj"), None)
    if sb_k is not None and obj_k is not None and sb_k > obj_k:
        b -= W_SBOBJ                     # Sb e' stato emesso dopo Obj: bonus perso

    return b

def search_order(combo: List[C], pred: Pred, base: int, lower_bound: Optional[int],
                  stats: Stats, tt: Dict[Tuple[int, ...], int]
                  ) -> Optional[Tuple[int, List[Item]]]:
    """Best-first B&B sull'ordine dei costituenti + predicato. `base' e' gia'
    calcolato dal chiamante (score_plan, che ora include anche il bonus di
    copertura dei semi). Determinismo per tie-break stabile (counter
    monotono, mai hash di set)."""
    items: List[Item] = list(combo) + [pred]
    n = len(items)

    best: Optional[Tuple[int, List[Item]]] = None
    counter = itertools.count()
    pq: List[Tuple[int, int, Tuple[int, ...], Tuple[int, ...]]] = []
    heapq.heappush(pq, (-(base + MAXORD), next(counter), (), tuple(range(n))))

    while pq:
        negb, _, emitted, rest = heapq.heappop(pq)
        bound = -negb
        stats.nodes += 1

        if best is not None and bound <= best[0]:
            stats.pruned_bound += 1
            continue
        if lower_bound is not None and bound < lower_bound:
            stats.pruned_bound += 1
            continue

        if not rest:
            seq = [items[i] for i in emitted]
            vi = next(i for i, x in enumerate(seq) if not isinstance(x, C))
            sc = base + order_score(seq, vi)
            if best is None or sc > best[0]:
                best = (sc, seq)
            continue

        key = tuple(sorted(emitted))
        if key in tt and tt[key] >= bound:
            stats.tt_hits += 1
        tt[key] = max(tt.get(key, -(10**9)), bound)

        for idx in sorted(rest):    # move ordering canonico: indice crescente => determinismo
            new_emitted = emitted + (idx,)
            new_rest = tuple(x for x in rest if x != idx)
            b = _admissible_bound(new_emitted, items, base)
            heapq.heappush(pq, (-b, next(counter), new_emitted, new_rest))

    return best

# ==========================================================================
# 8. Driver: Iterative Deepening con Aspiration Window (CLAUDE.md §3, §9)
#
# Input: SEMI su piu' parti del discorso (verbi, nomi, aggettivi), non un
# solo verbo. Universo di ricerca chiuso ai semi forniti (come nel prototipo
# originale, SemanticState). Obiettivo: la frase che massimizza il punteggio,
# che ora include esplicitamente quanti semi distinti sono stati incorporati
# — non necessariamente tutti (W_SEED, dichiarato in §4).
# ==========================================================================
def generate(verbs, nouns=(), adjs=(), num="sg", max_words=8):
    seed_verbs = tuple(verbs) if not isinstance(verbs, str) else (verbs,)
    seeds = frozenset(seed_verbs) | frozenset(nouns) | frozenset(adjs)
    if not seeds:
        return None, "nessun seme fornito"

    stats = Stats()
    trace: List[str] = []
    overall = None   # (score, seq, combo, frame, pred)
    aspiration: Optional[int] = None

    # frame canonici per ciascun possibile verbo che governa il predicato
    # (il lessicale, sia da solo sia sotto un modale — vedi build_predicates)
    frame_cache: Dict[str, list] = {}
    for v in seed_verbs:
        if v in D["verbs"]:
            frame_cache[v] = sorted(f for f in D["verbs"][v]["frames"]
                                     if canonical([tuple(s) for s in f]))

    for d in range(2, max_words + 1):
        tt: Dict[Tuple[int, ...], int] = {}
        best_this = None

        for pred in build_predicates(seed_verbs, num):
            gov = pred.lemmas[-1]
            frames = frame_cache.get(gov, [])
            budget = d - len(pred.words)
            if budget < 0:
                continue
            for frame in frames:
                fillers = D["verbs"][gov]["fillers"]
                for combo in enumerate_combos_seeded(frame, fillers, nouns, adjs,
                                                      num, budget, stats):
                    base = score_plan(combo, pred, seeds)
                    lb = aspiration if best_this is None else max(
                        aspiration if aspiration is not None else -(10**9), best_this[0])
                    r = search_order(combo, pred, base, lb, stats, tt)
                    if r is None:
                        continue
                    sc, seq = r
                    if best_this is None or sc > best_this[0]:
                        best_this = (sc, seq, combo, frame, pred)

        if best_this is not None:
            sc, seq, combo, frame, pred = best_this
            words = [w for x in seq for w in (x.words if isinstance(x, C) else x.words)]
            trace.append(f"depth {d}: score={sc}  «{' '.join(words)}»")
            aspiration = sc
            if overall is None or sc > overall[0]:
                overall = best_this
        else:
            trace.append(f"depth {d}: nessuna frase ammissibile")

    if overall is None:
        return None, f"nessuna realizzazione (semi: {sorted(seeds)})"

    sc, seq, combo, frame, pred = overall
    words = [w for x in seq for w in x.words]
    sentence = " ".join(words)
    used = (set(pred.lemmas) | {c.noun for c in combo} | {c.adj for c in combo if c.adj}) & seeds
    info = (f"nodi={stats.nodes} piani={stats.plans} "
            f"potati_bound={stats.pruned_bound} potati_gramm={stats.pruned_grammar} "
            f"tt_hits={stats.tt_hits} | semi usati {len(used)}/{len(seeds)}: {sorted(used)} | "
            + " / ".join(trace))
    return (sc, sentence, combo, frame, pred), info

# ==========================================================================
# 9. DIVINATIO — ricostruzione filologica (ADR-003 §I)
#
# Input: due estremi FISSI (prefix_tokens, suffix_tokens) e la lunghezza
# della lacuna in caratteri (gap_len_chars) — VINCOLO DURO sul bound, non un
# premio da massimizzare come in §8. Qui il bias di lunghezza si dissolve
# perche' la lunghezza non e' una variabile: e' un dato (misurabile su
# pietra/papiro), esattamente come dichiarato in ADR-003.
#
# Semplificazioni dichiarate per questa prima versione (non nascoste):
#   - il confine prefisso/lacuna e lacuna/suffisso deve cadere fra due
#     costituenti interi (predicato o sintagma), non a meta' di uno di essi;
#   - nessun aggettivo nella ricostruzione (solo teste nominali dei frame);
#   - la ricerca e' su TUTTI i filler attestati per lo slot (non su semi
#     forniti dall'utente: qui si cerca su tutto il corpus, come un filologo).
# ==========================================================================
@dataclass
class DivinatioStats:
    combos_tried: int = 0
    orderings_checked: int = 0
    pruned_length: int = 0
    valid_found: int = 0

def _all_fillers_combos(frame, fillers: Dict[str, List[str]], num: str):
    """Come enumerate_combos_seeded, ma senza restrizione a semi: tutti i
    filler ATTESTATI per lo slot sono candidati."""
    slots = [tuple(s) for s in frame]
    per = []
    for rel, case, prep in slots:
        key = "|".join((rel, case, prep))
        opts = []
        for nl in sorted(fillers.get(key, [])):
            c = build(rel, case, prep, nl, None, num)
            if c:
                opts.append(c)
        if not opts:
            return
        per.append(opts)
    for combo in itertools.product(*per):
        if len({c.noun for c in combo}) != len(combo):
            continue
        yield list(combo)

def reconstruct(verb: str, prefix_tokens: Tuple[str, ...], suffix_tokens: Tuple[str, ...],
                 gap_len_chars: int, num: str = "sg"):
    """Divinatio: saldare due estremi fissi. gap_len_chars e' un vincolo
    duro — solo le ricostruzioni che lo soddisfano ESATTAMENTE sono ammesse.
    Ritorna (score, sentence, combo, frame, pred, gap_words), info."""
    if verb not in D["verbs"]:
        return None, "verbo assente da ITVALEX∩GF"
    try:
        vw = conjugate(verb, GV[verb], num)
        pred = Pred((vw,), (verb,))
    except (Undecidable, KeyError) as ex:
        return None, f"UNDECIDABLE: {ex}"

    frames = sorted(f for f in D["verbs"][verb]["frames"] if canonical([tuple(s) for s in f]))
    if not frames:
        return None, "nessun frame canonico"

    prefix_tokens = tuple(prefix_tokens)
    suffix_tokens = tuple(suffix_tokens)
    stats = DivinatioStats()
    best = None   # (score, seq, combo, frame, mid_words)

    for frame in frames:
        fillers = D["verbs"][verb]["fillers"]
        for combo in _all_fillers_combos(frame, fillers, num):
            stats.combos_tried += 1
            items: List[Item] = list(combo) + [pred]
            n = len(items)

            for perm in itertools.permutations(range(n)):
                stats.orderings_checked += 1
                seq = [items[i] for i in perm]
                words = [w for it in seq for w in it.words]

                if len(words) < len(prefix_tokens) + len(suffix_tokens):
                    continue
                if prefix_tokens and tuple(words[:len(prefix_tokens)]) != prefix_tokens:
                    continue
                if suffix_tokens and tuple(words[len(words) - len(suffix_tokens):]) != suffix_tokens:
                    continue

                mid = words[len(prefix_tokens): len(words) - len(suffix_tokens)] \
                      if suffix_tokens else words[len(prefix_tokens):]
                if sum(len(w) for w in mid) != gap_len_chars:
                    stats.pruned_length += 1
                    continue

                stats.valid_found += 1
                vi = next(i for i, x in enumerate(seq) if not isinstance(x, C))
                sc = score_plan(combo, pred, frozenset()) + order_score(seq, vi)
                if best is None or sc > best[0]:
                    best = (sc, seq, combo, frame, mid)

    info_base = (f"combinazioni={stats.combos_tried} ordini_controllati={stats.orderings_checked} "
                 f"scartati_per_lunghezza={stats.pruned_length} ricostruzioni_valide={stats.valid_found}")

    if best is None:
        return None, f"nessuna ricostruzione soddisfa prefisso/suffisso/lunghezza esatta | {info_base}"

    sc, seq, combo, frame, mid = best
    sentence = " ".join(w for it in seq for w in it.words)
    return (sc, sentence, combo, frame, pred, tuple(mid)), info_base
