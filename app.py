"""
Machina — interfaccia dimostrativa (Hugging Face Spaces).

PRINCIPIO DI DESIGN:
  La frase non è il prodotto. La TRACCIA è il prodotto.
  Un LLM produce una frase e nasconde il perché. Machina espone il perché e la
  frase è un corollario. La demo deve rendere visibile esattamente questo:
  albero, valenza, punteggio scomposto, nodi esplorati, nodi potati, e il
  fingerprint che prova il determinismo.

TEMA:
  Chiaro, monospace (Consolas — coerente con l'estetica "traccia/log" del
  progetto). Un solo colore d'accento, il bordeaux: niente palette multipla.
  Le variabili CSS di Gradio vengono sovrascritte direttamente (non solo
  tramite l'API Theme.set(), che lascia scoperti alcuni sfondi secondari
  usati dai blocchi di codice/pannelli — con testo forzato scuro sopra uno
  sfondo rimasto scuro di default, il risultato era illeggibile) e forzate
  anche sotto `.dark`, cosi' il tema resta chiaro a prescindere dalle
  preferenze del sistema/browser di chi apre il link.
"""
import hashlib
import gradio as gr

from machina import machina_real as M
from machina import resources as R

BORDEAUX   = "#6E2A34"
BORDEAUX_H = "#551F27"   # hover, piu' scuro
INCHIOSTRO = "#1C1C1A"
CARTA      = "#FFFFFF"
PANNELLO   = "#F7F5F1"   # sfondo secondario (blocchi di codice ecc.), chiaro
BORDO      = "#DEDACF"

THEME = gr.themes.Base().set(
    body_background_fill=CARTA,
    body_text_color=INCHIOSTRO,
    background_fill_primary=CARTA,
    background_fill_secondary=PANNELLO,
    block_background_fill=CARTA,
    block_border_color=BORDO,
    block_title_text_color=BORDEAUX,
    block_label_text_color=BORDEAUX,
    border_color_primary=BORDO,
    button_primary_background_fill=BORDEAUX,
    button_primary_background_fill_hover=BORDEAUX_H,
    button_primary_text_color="#FFFFFF",
    button_primary_border_color=BORDEAUX,
    input_background_fill=CARTA,
    input_border_color=BORDO,
    input_border_color_focus=BORDEAUX,
    slider_color=BORDEAUX,
    link_text_color=BORDEAUX,
    link_text_color_hover=BORDEAUX_H,
)

# Sovrascrittura diretta delle custom property CSS di Gradio, anche sotto
# .dark: l'API Python del tema non copre tutte le variabili usate dai
# componenti (es. gli sfondi dei blocchi ```codice``` in Markdown), quindi
# si forzano qui i valori effettivi, non solo quelli esposti da Theme.set().
CSS = f"""
* {{ font-family: 'Consolas', ui-monospace, SFMono-Regular, monospace !important; }}

:root, .dark, .gradio-container {{
  --body-background-fill: {CARTA} !important;
  --background-fill-primary: {CARTA} !important;
  --background-fill-secondary: {PANNELLO} !important;
  --block-background-fill: {CARTA} !important;
  --panel-background-fill: {CARTA} !important;
  --body-text-color: {INCHIOSTRO} !important;
  --body-text-color-subdued: #55524c !important;
  --block-title-text-color: {BORDEAUX} !important;
  --block-label-text-color: {BORDEAUX} !important;
  --border-color-primary: {BORDO} !important;
  --border-color-accent: {BORDEAUX} !important;
  --button-primary-background-fill: {BORDEAUX} !important;
  --button-primary-background-fill-hover: {BORDEAUX_H} !important;
  --button-primary-text-color: #FFFFFF !important;
  --input-background-fill: {CARTA} !important;
  --link-text-color: {BORDEAUX} !important;
  --code-background-fill: {PANNELLO} !important;
  --table-even-background-fill: {CARTA} !important;
  --table-odd-background-fill: {PANNELLO} !important;
}}
h1 {{ color: {BORDEAUX}; }}
"""


def run(verb_list, noun_list, adj_list, num: str, depth: int):
    verbs = tuple(verb_list or [])
    nouns = tuple(noun_list or [])
    adjs = tuple(adj_list or [])

    if not verbs:
        return "—", "Scegli almeno un verbo: è il seme che ancora il predicato.", "", ""

    res, info = M.generate(verbs=verbs, nouns=nouns, adjs=adjs, num=num, max_words=depth)
    if not res:
        return "—", f"Nessuna realizzazione trovata.\n\n`{info}`", "", ""

    score, sent, plan, frame, pred = res
    gov = pred.lemmas[-1]   # il verbo lessicale che governa il frame

    src = "GF DictLat"
    try:
        M.verb_conj(gov, M.GV[gov])
    except (M.Undecidable, KeyError):
        if gov in R.verbs:
            src = f"Whitaker (conj. {R.verbs[gov]['conj']}) — GF era indecidibile"

    modale = (f" · composto con verbo servile/fraseologico **{pred.lemmas[0]}** "
              f"(tabella dichiarata, non indovinata — vedi `machina/machina_real.py` §2bis)"
              if len(pred.lemmas) > 1 else "")

    # --- valenza e restrizioni selettive
    val = ["| funtore | caso | prep | filler | attestato | tassonomia (LWN) |",
           "|---|---|---|---|---|---|"]
    for c in plan:
        tx = len(R.taxon_of(c.noun))
        val.append(f"| `{c.rel}` | {c.case} | {c.prep or '—'} | **{c.noun}** "
                   f"| IT-VaLex ✓ | {tx} antenati |")

    # --- albero
    tree = ["```", "(S"]
    for c in plan:
        tree.append(f"   (NP:{c.rel}.{c.case}  {' '.join(c.words)})")
    tree += [f"   (VP  {' '.join(pred.words)})", ")", "```"]

    # --- determinismo: fingerprint riproducibile (include le statistiche di ricerca)
    fp = hashlib.sha256(
        f"{sorted(verbs)}|{sorted(nouns)}|{sorted(adjs)}|{num}|{depth}|{sent}|{score}|{info}".encode()
    ).hexdigest()[:16]

    trace = (
        f"**Predicato:** `{' '.join(pred.words)}` — coniugazione da {src}{modale}\n\n"
        f"**Frame valenziale ({gov}):** `{[tuple(s) for s in frame]}`\n\n"
        f"**Ricerca (best-first + Branch & Bound, TT, Iterative Deepening):** {info}\n\n"
        f"**Punteggio:** {score}  *(interi puri — nessun float: "
        f"la somma in virgola mobile non è associativa e aprirebbe una falla "
        f"nel determinismo; include il bonus dichiarato per semi incorporati)*\n\n"
        f"**Fingerprint SHA-256:** `{fp}`\n\n"
        f"> Riesegui con gli stessi parametri: il fingerprint sarà identico. "
        f"Sempre — include anche le statistiche di ricerca, non solo la frase. "
        f"È l'unica garanzia che questo non sia un modello linguistico."
    )
    return sent, trace, "\n".join(val), "\n".join(tree)


def run_divinatio(verb: str, prefix_str: str, suffix_str: str, gap_len: int, num: str):
    if not verb:
        return "—", "Scegli un verbo.", ""
    prefix = tuple(t.strip() for t in prefix_str.split() if t.strip())
    suffix = tuple(t.strip() for t in suffix_str.split() if t.strip())

    res, info = M.reconstruct(verb, prefix, suffix, int(gap_len), num=num)
    if not res:
        return "—", f"Nessuna ricostruzione trovata.\n\n`{info}`", ""

    score, sentence, combo, frame, pred, mid = res
    mid_len = sum(len(w) for w in mid)
    trace = (
        f"**Lacuna ricostruita:** `{' '.join(mid)}`  ({mid_len} caratteri — richiesti esattamente {int(gap_len)})\n\n"
        f"**Frame valenziale ({verb}):** `{[tuple(s) for s in frame]}`\n\n"
        f"**Ricerca (vincolo duro su prefisso/suffisso/lunghezza, non premio):** {info}\n\n"
        f"**Punteggio:** {score}\n\n"
        f"> A differenza della generazione libera, qui la lunghezza non è una "
        f"variabile da massimizzare: è un dato (il numero di caratteri misurabile "
        f"sulla pietra/papiro). Il bias di lunghezza non si presenta per questo motivo."
    )
    val = ["| funtore | caso | filler ricostruito | attestato |", "|---|---|---|---|"]
    for c in combo:
        val.append(f"| `{c.rel}` | {c.case} | **{c.noun}** | IT-VaLex ✓ |")
    return sentence, trace, "\n".join(val)


VERBS = sorted((set(M.D["verbs"]) & (set(M.GV) | set(R.verbs))) | set(M.PHRASAL_VERBS))
NOUNS = sorted({n for v in M.D["verbs"].values() for ns in v["fillers"].values() for n in ns})
ADJS  = sorted(M.GA)
DIV_VERBS = sorted(M.D["verbs"].keys() & set(M.GV))

with gr.Blocks(title="Machina") as demo:
    gr.Markdown(
        "# Machina\n\n"
        "Genera frasi latine grammaticalmente corrette **cercandole** fra le "
        "possibilità attestate in corpora reali (non prevedendole con un "
        "modello linguistico), e mostra sempre il percorso completo che ha "
        "portato a quella frase — non solo il risultato.\n\n"
        "**Come si usa:**\n"
        "1. Scegli uno o più **verbi** (il predicato — se ne scegli più di uno "
        "sono candidati fra cui il motore sceglie; scegli anche un verbo "
        "servile come **debeo** insieme a un altro verbo per ottenere un "
        "predicato composto tipo *debet amare*).\n"
        "2. Scegli uno o più **nomi** e uno o più **aggettivi**: sono i semi "
        "semantici — il motore userà quelli grammaticalmente compatibili e "
        "attestati nel corpus, **non necessariamente tutti**.\n"
        "3. Scegli il **numero** (singolare o plurale).\n"
        "4. Regola la **profondità** (`go depth N`): il numero massimo di "
        "parole della frase generata.\n"
        "5. Premi **generate**.\n\n"
        "**Cosa vedi nel risultato:** la frase latina; la traccia (predicato "
        "scelto e da dove viene la sua coniugazione, quale frame valenziale è "
        "stato usato, quanti semi dei tuoi sono stati effettivamente "
        "incorporati, quanti nodi la ricerca ha esplorato e potato, il "
        "punteggio, e un *fingerprint* — riesegui con gli stessi parametri e "
        "resta identico: è la prova che il risultato non dipende dal caso); "
        "la tabella di **valenza** (quali ruoli il verbo richiede e con quali "
        "nomi sono realmente attestati nel corpus); l'**albero sintattico**.\n\n"
        "Non tutte le combinazioni funzionano: un nome/aggettivo entra in "
        "frase solo se attestato per quello slot di quel verbo nel corpus "
        "usato, e solo i verbi con coniugazione ricavabile senza ambiguità "
        "sono utilizzabili da soli — se compare `UNDECIDABLE`, è voluto: il "
        "motore preferisce rifiutarsi piuttosto che indovinare una forma."
    )

    with gr.Tabs():
        with gr.Tab("Genera da semi"):
            with gr.Row():
                with gr.Column(scale=1):
                    verb = gr.Dropdown(VERBS, value=["amo"] if "amo" in VERBS else VERBS[:1],
                                       multiselect=True, label="Verbi (predicato)")
                    noun = gr.Dropdown(NOUNS, value=[v for v in ["deus", "homo"] if v in NOUNS],
                                       multiselect=True, label="Nomi (semi)")
                    adjs = gr.Dropdown(ADJS, value=[v for v in ["bonus", "magnus"] if v in ADJS],
                                       multiselect=True, label="Aggettivi (semi)")
                    num = gr.Radio(["sg", "pl"], value="sg", label="Numero")
                    depth = gr.Slider(3, 10, 8, step=1, label="go depth N (parole massime)")
                    btn = gr.Button("generate", variant="primary")
                with gr.Column(scale=2):
                    out = gr.Textbox(label="Frase latina", lines=1)
                    tr = gr.Markdown(label="Traccia")
            with gr.Row():
                vl = gr.Markdown(label="Valenza e restrizioni selettive")
                tv = gr.Markdown(label="Albero sintattico")
            btn.click(run, [verb, noun, adjs, num, depth], [out, tr, vl, tv])

        with gr.Tab("Divinatio — ricostruzione"):
            gr.Markdown(
                "Ricostruisce la **lacuna** fra due estremi già noti (prefisso e "
                "suffisso attestati), dato il numero esatto di caratteri mancanti "
                "— come in epigrafia/papirologia, dove l'ampiezza della lacuna è "
                "misurabile. **Qui la lunghezza è un vincolo, non un obiettivo da "
                "massimizzare.** Su un test di 86 casi (frase attestata cancellata "
                "artificialmente), Machina trova una ricostruzione grammaticalmente "
                "valida nel 98.8% dei casi e recupera la lezione esatta nel 76.7%."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    dv_verb = gr.Dropdown(DIV_VERBS, value="amo" if "amo" in DIV_VERBS else DIV_VERBS[0],
                                          label="Verbo (già noto/ipotizzato dal contesto)")
                    dv_prefix = gr.Textbox("homo", label="Prefisso (parole già note, separate da spazio)")
                    dv_suffix = gr.Textbox("amat", label="Suffisso (parole già note, separate da spazio)")
                    dv_gap = gr.Slider(1, 20, 9, step=1, label="Lunghezza della lacuna (caratteri)")
                    dv_num = gr.Radio(["sg", "pl"], value="sg", label="Numero")
                    dv_btn = gr.Button("reconstruct", variant="primary")
                with gr.Column(scale=2):
                    dv_out = gr.Textbox(label="Ricostruzione", lines=1)
                    dv_tr = gr.Markdown(label="Traccia")
            dv_vl = gr.Markdown(label="Valenza dei costituenti ricostruiti")
            dv_btn.click(run_divinatio, [dv_verb, dv_prefix, dv_suffix, dv_gap, dv_num],
                        [dv_out, dv_tr, dv_vl])

    gr.Markdown(
        "---\n"
        "**Le restrizioni selettive sono a due livelli, entrambi logici:**\n\n"
        "1. **Attestazione** (IT-VaLex): usare le *frequenze* di un corpus come "
        "pesi sarebbe statistica — vietato. Usare l'*attestazione* come predicato "
        "booleano è una relazione logica — ammesso. Machina legge il corpus "
        "**come un dizionario, non come una distribuzione**.\n"
        "2. **Copertura dei semi**: la ricerca premia esplicitamente quanti dei "
        "nomi/aggettivi/verbi scelti compaiono nella frase finale — non è un "
        "requisito tutto-o-niente: alcuni semi possono restare esclusi se non "
        "grammaticalmente compatibili con nessun frame disponibile.\n\n"
        "**Limiti dichiarati:** la funzione di valutazione premia anche la "
        "lunghezza della frase, non solo la copertura dei semi — non si "
        "presenta in Divinatio, dove la lunghezza della lacuna è nota; i frame "
        "di IT-VaLex sono indotti da parse e contengono artefatti; i verbi "
        "servili disponibili sono solo quelli dichiarati esplicitamente in "
        "`machina/machina_real.py` (**debeo** oggi — **possum**/**volo** sono "
        "esclusi per collisioni/lacune nei dati, non dimenticati). Documentato "
        "in `docs/ADR-001.md`.\n\n"
        "Codice **CC0** · dati **non ridistribuiti** (vedi `NOTICE.md`)"
    )

if __name__ == "__main__":
    import os
    demo.launch(theme=THEME, css=CSS, share=os.environ.get("MACHINA_SHARE") == "1")
