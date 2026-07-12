"""
FASE 0 — Estrazione dalle risorse reali. Rigenera data/data_real.json.

  ITVALEX (GPL-3, CIRCSE)  -> frame valenziali + filler ATTESTATI
  GF DictLat (LGPL, RGL)   -> paradigmi morfologici (36k lemmi, da Whitaker's WORDS)

NOTA EPISTEMOLOGICA (decisiva per i vincoli del progetto):
  Usare le FREQUENZE del corpus come pesi sarebbe statistica -> VIETATO.
  Usare l'ATTESTAZIONE come predicato booleano (questo lemma e' attestato in
  questo slot di questo verbo) e' una RELAZIONE LOGICA -> ammesso.
  Machina legge il corpus come un dizionario, non come una distribuzione.

Non versionato: `data/data_real.json` che questo script produce e' derivato
da IT-VaLex (GPL-3) e non va committato (NOTICE.md, CLAUDE.md §5). Il repo
resta CC0 perche' non incorpora il dato: lo rigenera da fonte, on demand.

Uso:
  ./scripts/fetch_resources.sh --profile research   # scarica ITVALEX + GF
  python -m machina.build
"""
import re, json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL = ROOT / "data" / "src" / "itvalex" / "itvalexdb.sql"
GF = ROOT / "data" / "src" / "gf-rgl" / "src" / "latin" / "DictLat.gf"
OUT = ROOT / "data" / "data_real.json"

# --------------------------------------------------------------------------
# 1. Parser di INSERT MySQL (senza dipendenze)
# --------------------------------------------------------------------------
ROW = re.compile(r"\(((?:[^()']|'(?:[^'\\]|\\.)*')*)\)")

def split_row(s):
    out, cur, q, esc = [], [], False, False
    for ch in s:
        if esc:
            cur.append(ch); esc = False; continue
        if ch == "\\":
            esc = True; continue
        if ch == "'":
            q = not q; continue
        if ch == "," and not q:
            out.append("".join(cur)); cur = []; continue
        cur.append(ch)
    out.append("".join(cur))
    return [x.strip() for x in out]

def iter_inserts(path, table):
    pat = f"INSERT INTO `{table}` VALUES "
    with open(path, encoding="latin-1") as f:
        for line in f:
            if line.startswith(pat):
                for m in ROW.finditer(line[len(pat):]):
                    yield split_row(m.group(1))

# --------------------------------------------------------------------------
# 2. Forma: ID -> (forma, lemma, pos, caso, afun)
# --------------------------------------------------------------------------
forma = {}
for r in iter_inserts(SQL, "Forma"):
    # ID, forma, lemma, pos, grado_nom, cat_fl, modo, tempo, grado_part,
    # caso, gen_num, comp, variaz, variaz_graf, afun, rank, gov, frase
    forma[r[0]] = (r[1], r[2], r[3], r[9], r[14])
print(f"Forma       : {len(forma):>7} token annotati", file=sys.stderr)

# --------------------------------------------------------------------------
# 3. VerbArgument -> frame + filler attestati
# --------------------------------------------------------------------------
frames  = defaultdict(set)                   # verbo -> {frame come tupla ordinata}
fillers = defaultdict(lambda: defaultdict(set))  # verbo -> (rel,case,prep) -> {lemmi}
by_root = defaultdict(list)

n = 0
for r in iter_inserts(SQL, "VerbArgument"):
    # root_id, arg_id, coord_id, mn, mx, relation, rCase, lemma, prep, conj
    root, rel, rcase, lem, prep = r[0], r[5], r[6], r[7], r[8]
    by_root[root].append((rel, rcase, lem, prep))
    n += 1
print(f"VerbArgument: {n:>7} argomenti,  {len(by_root)} occorrenze verbali", file=sys.stderr)

for root, args in by_root.items():
    if root not in forma:
        continue
    vlem = forma[root][1]
    if not vlem or vlem == "NULL":
        continue
    slots = []
    for rel, rcase, lem, prep in args:
        if rel in ("NULL", "", None):
            continue
        prep = "" if prep in ("NULL", None) else prep
        rcase = "" if rcase in ("NULL", None) else rcase
        slots.append((rel, rcase, prep))
        if lem and lem != "NULL":
            fillers[vlem][(rel, rcase, prep)].add(lem)
    if slots:
        frames[vlem].add(tuple(sorted(slots)))

# --------------------------------------------------------------------------
# 4. GF DictLat -> paradigmi
#
# ⚠ Deve catturare anche mkV2/mkV3 (i transitivi!), non solo mkV: altrimenti
# si perde meta' del lessico verbale (ADR-001 §2a — la collisione lego/lego2).
# A parita' di lemma, si preferisce l'entrata con PIU' forme: e' cosi' che si
# risolve l'omografo lego_V (legare) / lego_V2 (legere). Stessa regola gia'
# applicata in machina_real.load_gf(): tenerle allineate, non e' un dettaglio
# locale a un modulo.
# --------------------------------------------------------------------------
gf = {"N": {}, "A": {}, "V": {}}
reN = re.compile(r'^\s*(\w+?)_(?:F_N|M_N|N_N|N)\d*\s*=\s*mkN\s+(.*?)\s*;')
reA = re.compile(r'^\s*(\w+?)_A\d*\s*=\s*mkA\s+(.*?)\s*;')
reV = re.compile(r'^\s*(\w+?)_V\d?\d*\s*=\s*(?:mkV[23]?\s*\(\s*)?mkV\s+(.*)')
with open(GF, encoding="utf-8", errors="replace") as f:
    for line in f:
        if (m := reN.match(line)):
            forms = re.findall(r'"([^"]+)"', m.group(2))
            gender = ("masculine" in m.group(2) and "m") or ("feminine" in m.group(2) and "f") \
                     or ("neuter" in m.group(2) and "n") or ""
            if forms and (m.group(1) not in gf["N"] or len(forms) > len(gf["N"][m.group(1)]["forms"])):
                gf["N"][m.group(1)] = {"forms": forms, "gender": gender}
        elif (m := reA.match(line)):
            forms = re.findall(r'"([^"]+)"', m.group(2))
            if forms and (m.group(1) not in gf["A"] or len(forms) > len(gf["A"][m.group(1)]["forms"])):
                gf["A"][m.group(1)] = {"forms": forms, "gender": ""}
        elif (m := reV.match(line)):
            forms = re.findall(r'"([^"]+)"', m.group(2))
            if forms and (m.group(1) not in gf["V"] or len(forms) > len(gf["V"][m.group(1)]["forms"])):
                gf["V"][m.group(1)] = {"forms": forms, "gender": ""}
print(f"GF DictLat  : N={len(gf['N'])}  A={len(gf['A'])}  V={len(gf['V'])}",
      file=sys.stderr)

# --------------------------------------------------------------------------
# 5. Intersezione: cio' su cui Machina puo' effettivamente lavorare
# --------------------------------------------------------------------------
verbs_both = sorted(set(frames) & set(gf["V"]))
noun_lemmas = {l for v in fillers for s in fillers[v] for l in fillers[v][s]}
nouns_both = sorted(noun_lemmas & set(gf["N"]))

print(f"\nINTERSEZIONE ITVALEX ∩ GF:", file=sys.stderr)
print(f"  verbi con frame + paradigma : {len(verbs_both)}", file=sys.stderr)
print(f"  nomi filler con paradigma   : {len(nouns_both)}", file=sys.stderr)

out = {
    "verbs": {v: {"frames": sorted(list(f) for f in frames[v]),
                  "fillers": {"|".join(k): sorted(fillers[v][k])
                              for k in sorted(fillers[v])},
                  "paradigm": gf["V"][v]["forms"]}
              for v in verbs_both},
    "nouns": {n: gf["N"][n] for n in nouns_both},
    "adjs":  {a: gf["A"][a] for a in sorted(gf["A"])},
}
OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w") as f:
    json.dump(out, f, ensure_ascii=False)
print(f"\n-> {OUT}", file=sys.stderr)
