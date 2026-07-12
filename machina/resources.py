"""
MACHINA — Integrazione risorse. Politica: open source, ready to use.

  (A) Whitaker's WORDS / DICTLINE.GEN   [PUBBLICO DOMINIO]
      Classe flessiva ESPLICITA + 4 temi principali.
      -> elimina l'indecidibilita' del 39% dei verbi.

  (B) Latin WordNet revision / CIRCSE   [lwn31.ttl]
      13.868 relazioni wn:hypernym, riviste a mano su OLD/Lewis&Short/Georges.
      -> E' LA TASSONOMIA. Non va scritta: esiste.
"""
import re, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DICT = ROOT / "data" / "src" / "whitakers-words" / "DICTLINE.GEN"
TTL = ROOT / "data" / "src" / "latin-wordnet" / "lwn31.ttl"

# ==========================================================================
# (A) WHITAKER — 4 temi da 19 caratteri, poi POS e classe flessiva
# ==========================================================================
WCONJ = {("1","1"):"1", ("2","1"):"2", ("3","1"):"3",
         ("3","2"):"3io", ("3","3"):"3", ("3","4"):"4"}
V1SG  = {"1":"o", "2":"eo", "3":"o", "3io":"io", "4":"io"}

verbs, nouns, adjs = {}, {}, {}

for line in open(DICT, encoding="latin-1"):
    line = line.rstrip("\r\n")
    if len(line) < 90: continue
    s = [line[i:i+19].strip() for i in (0, 19, 38, 57)]
    tail = line[76:100].split()
    if not tail or not s[0]: continue
    pos = tail[0]
    if pos == "V" and len(tail) >= 3:
        c = WCONJ.get((tail[1], tail[2]))
        if not c: continue
        dep = len(tail) >= 4 and tail[3] == "DEP"      # deponenti: 1sg in -or
        lemma = s[0] + V1SG[c] + ("r" if dep else "")
        verbs.setdefault(lemma, {"stems": s, "conj": c, "dep": dep})
    elif pos == "N" and len(tail) >= 4:
        d, g = tail[1], tail[3].lower()
        if d not in "12345": continue
        nouns.setdefault(s[0], {"nom": s[0], "stem": s[1] or s[0],
                                "decl": d, "gender": g if g in "mfn" else "c"})
    elif pos == "ADJ":
        adjs.setdefault(s[0], {"stem": s[1] or s[0]})

print(f"[A] Whitaker : V={len(verbs)}  N={len(nouns)}  ADJ={len(adjs)}", file=sys.stderr)

# ==========================================================================
# (B) LATIN WORDNET — parser Turtle a blocchi
# ==========================================================================
lemma2syn = defaultdict(set)
hyper     = defaultdict(set)

_txt = re.sub(r"^@prefix.*$", "", open(TTL, encoding="utf-8", errors="replace").read(), flags=re.M)
_SYN = re.compile(r"wordnetSynset:[\w\-]+")

for stmt in re.split(r"\.\s*\n", _txt):
    stmt = stmt.strip()
    if not stmt: continue
    subj = stmt.split(None, 1)[0]
    if subj.startswith("wordnetSynset:"):
        for h in re.findall(r"wn:hypernym\s+([^;]+)", stmt):
            hyper[subj].update(_SYN.findall(h))
    elif subj.startswith("wordnetLexicalEntry:"):
        w = re.search(r'(?:writtenRep\w*|rdfs:label)\s+"([^"]+)"', stmt)
        if not w: continue
        lem = w.group(1).strip().lower()
        for ev in re.findall(r"ontolex:evokes\s+([^;]+)", stmt):
            lemma2syn[lem].update(_SYN.findall(ev))

print(f"[B] LatinWN  : lemmi={len(lemma2syn)}  synset con iperonimo={len(hyper)}",
      file=sys.stderr)

# ==========================================================================
# Operazioni tassonomiche (deterministiche: iterazione su insiemi ordinati)
# ==========================================================================
def ancestors(syn, depth=12):
    seen, front = set(), {syn}
    for _ in range(depth):
        nxt = set()
        for s in sorted(front):
            for h in sorted(hyper.get(s, ())):
                if h not in seen:
                    seen.add(h); nxt.add(h)
        if not nxt: break
        front = nxt
    return seen

def taxon_of(lemma):
    out = set()
    for s in sorted(lemma2syn.get(lemma.lower(), ())):
        out.add(s); out |= ancestors(s)
    return out

def subsumes(sup_lemma, sub_lemma):
    """sub ⊂ sup ?  Generalizza le restrizioni selettive: un filler NON attestato
    e' comunque ammesso se e' IPONIMO di un filler attestato."""
    sup = set(lemma2syn.get(sup_lemma.lower(), ()))
    return bool(sup & taxon_of(sub_lemma))
