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
# 4. Costituenti e valutazione (interi puri)
# ==========================================================================
@dataclass(frozen=True)
class C:
    rel: str; noun: str; adj: Optional[str]; case: str; num: str
    prep: str; words: Tuple[str, ...]

Item = Union[C, str]   # str = la forma coniugata del verbo

W_SLOT, W_ADJ = 40, 8
W_VFIN, W_SBOBJ, W_SB1ST = 15, 10, 8
MAXORD = W_VFIN + W_SBOBJ + W_SB1ST

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

def score_plan(combo: List[C]) -> int:
    """Componente indipendente dall'ordine."""
    return sum(W_SLOT + (W_ADJ if c.adj else 0) for c in combo)

def order_score(items: List[Item], vi: int) -> int:
    """Componente dipendente dall'ordine ('eleganza strutturale', CLAUDE.md §7)."""
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
# 6. Enumerazione dei piani (verbo+frame fissati; filler e modificatori variano)
# ==========================================================================
def enumerate_combos(frame, fillers: Dict[str, List[str]], adjs: Tuple[str, ...],
                      num: str, max_words: int, stats: Stats):
    slots = [tuple(s) for s in frame]
    per = []
    for rel, case, prep in slots:
        key = "|".join((rel, case, prep))
        cands = fillers.get(key, [])
        opts = []
        for nl in sorted(cands):
            for al in (None,) + tuple(sorted(adjs)):
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
        nw = sum(len(c.words) for c in combo) + 1
        if nw > max_words:
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

def search_order(combo: List[C], vw: str, lower_bound: Optional[int],
                  stats: Stats, tt: Dict[Tuple[int, ...], int]
                  ) -> Optional[Tuple[int, List[Item]]]:
    """Best-first B&B sull'ordine dei costituenti + verbo. Determinismo per
    tie-break stabile (counter monotono, mai hash di set)."""
    items: List[Item] = list(combo) + [vw]
    n = len(items)
    base = score_plan(combo)

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
# ==========================================================================
def generate(verb, num="sg", adjs=(), max_words=6):
    if verb not in D["verbs"]:
        return None, "verbo assente da ITVALEX∩GF"
    e = D["verbs"][verb]
    try:
        vw = conjugate(verb, GV[verb], num)
    except (Undecidable, KeyError) as ex:
        return None, f"UNDECIDABLE: {ex}"

    frames = [f for f in e["frames"] if canonical([tuple(s) for s in f])]
    if not frames:
        return None, "nessun frame canonico"
    frames = sorted(frames)

    stats = Stats()
    trace: List[str] = []
    overall: Optional[Tuple[int, List[Item], List[C], list]] = None
    aspiration: Optional[int] = None

    for d in range(2, max_words + 1):
        tt: Dict[Tuple[int, ...], int] = {}
        best_this: Optional[Tuple[int, List[Item], List[C], list]] = None

        for frame in frames:
            for combo in enumerate_combos(frame, e["fillers"], adjs, num, d, stats):
                lb = aspiration if best_this is None else max(
                    aspiration if aspiration is not None else -(10**9), best_this[0])
                r = search_order(combo, vw, lb, stats, tt)
                if r is None:
                    continue
                sc, seq = r
                if best_this is None or sc > best_this[0]:
                    best_this = (sc, seq, combo, frame)

        if best_this is not None:
            sc, seq, combo, frame = best_this
            words = [w for x in seq for w in (x.words if isinstance(x, C) else (x,))]
            trace.append(f"depth {d}: score={sc}  «{' '.join(words)}»")
            aspiration = sc
            if overall is None or sc > overall[0]:
                overall = best_this
        else:
            trace.append(f"depth {d}: nessuna frase ammissibile")

    if overall is None:
        return None, "nessuna realizzazione"

    sc, seq, combo, frame = overall
    words = [w for x in seq for w in (x.words if isinstance(x, C) else (x,))]
    sentence = " ".join(words)
    info = (f"nodi={stats.nodes} piani={stats.plans} "
            f"potati_bound={stats.pruned_bound} potati_gramm={stats.pruned_grammar} "
            f"tt_hits={stats.tt_hits} frame_canonici={len(frames)} | "
            + " / ".join(trace))
    return (sc, sentence, combo, frame), info
