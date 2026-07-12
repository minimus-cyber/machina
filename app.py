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
  progetto: la trasparenza si legge meglio in un font da codice che in uno
  editoriale). Palette dichiarata, non decorativa: verde mimetico come colore
  dominante, bordeaux per titoli/enfasi, rosa carne/ciano/viola chiaro come
  accenti minori — usati per distinguere le componenti del punteggio (SEM,
  TAX, SYN, ORD), non a caso.
"""
import hashlib
import gradio as gr

from machina import machina_real as M
from machina import resources as R

# --- palette dichiarata (ordine di preferenza, non tutte obbligatorie) -----
VERDE_MIMETICO = "#5C6B47"
ROSA_CARNE     = "#D9A98A"
BORDEAUX       = "#6E2A34"
CIANO          = "#3F9DA8"
VIOLA_CHIARO   = "#B6A0D6"

INCHIOSTRO = "#1C1C1A"
CARTA      = "#FAFAF7"
BORDO      = "#DEDACF"

THEME = gr.themes.Base().set(
    body_background_fill=CARTA,
    body_background_fill_dark=CARTA,
    body_text_color=INCHIOSTRO,
    body_text_color_dark=INCHIOSTRO,
    block_background_fill="#FFFFFF",
    block_background_fill_dark="#FFFFFF",
    block_border_color=BORDO,
    block_title_text_color=BORDEAUX,
    block_label_text_color=BORDEAUX,
    button_primary_background_fill=VERDE_MIMETICO,
    button_primary_background_fill_hover="#4A5739",
    button_primary_text_color="#FFFFFF",
    button_primary_border_color=VERDE_MIMETICO,
    input_background_fill="#FFFFFF",
    input_border_color=BORDO,
    input_border_color_focus=BORDEAUX,
    slider_color=VERDE_MIMETICO,
    link_text_color=CIANO,
    link_text_color_hover=BORDEAUX,
)

CSS = f"""
* {{ font-family: 'Consolas', ui-monospace, SFMono-Regular, monospace !important; }}
h1 {{ color: {BORDEAUX}; }}
.machina-tag-sem {{ color: {VERDE_MIMETICO}; font-weight: bold; }}
.machina-tag-tax {{ color: {CIANO}; font-weight: bold; }}
.machina-tag-ord {{ color: {ROSA_CARNE}; font-weight: bold; }}
.machina-tag-fp  {{ color: {VIOLA_CHIARO}; }}
"""


def run(verb: str, num: str, adj_str: str, depth: int):
    adjs = tuple(a.strip() for a in adj_str.split(",") if a.strip())

    if verb not in M.D["verbs"]:
        return "—", f"Il verbo **{verb}** non è in IT-VaLex ∩ GF.", "", ""

    # coniugazione: Whitaker se GF non basta
    src = "GF DictLat"
    try:
        M.verb_conj(verb, M.GV[verb])
    except M.Undecidable:
        if verb in R.verbs:
            src = f"Whitaker (conj. {R.verbs[verb]['conj']}) — GF era indecidibile"
        else:
            return "—", (f"**{verb}**: coniugazione indecidibile.\n\n"
                         "Verbo irregolare (composto di *esse* o deponente anomalo): "
                         "richiede tabella esplicita.\n\n"
                         "*Il motore si rifiuta di indovinare. Un sistema che "
                         "indovinasse qui sarebbe deterministico e sbagliato.*"), "", ""

    res, info = M.generate(verb, num, adjs=adjs, max_words=depth)
    if not res:
        return "—", f"Nessuna realizzazione: {info}", "", ""

    score, sent, plan, frame = res

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
    tree += [f"   (V  {sent.split()[-1]})", ")", "```"]

    # --- determinismo: fingerprint riproducibile (include le statistiche di ricerca)
    fp = hashlib.sha256(f"{verb}|{num}|{sorted(adjs)}|{depth}|{sent}|{score}|{info}".encode()
                        ).hexdigest()[:16]

    trace = (
        f"**Coniugazione da:** {src}\n\n"
        f"**Frame valenziale:** `{[tuple(s) for s in frame]}`\n\n"
        f"**Ricerca (best-first + Branch & Bound, TT, Iterative Deepening):** {info}\n\n"
        f"**Punteggio:** {score}  *(interi puri — nessun float: "
        f"la somma in virgola mobile non è associativa e aprirebbe una falla "
        f"nel determinismo)*\n\n"
        f"<span class='machina-tag-fp'>**Fingerprint SHA-256:**</span> `{fp}`\n\n"
        f"> Riesegui con gli stessi parametri: il fingerprint sarà identico. "
        f"Sempre — include anche le statistiche di ricerca, non solo la frase. "
        f"È l'unica garanzia che questo non sia un modello linguistico."
    )
    return sent, trace, "\n".join(val), "\n".join(tree)


VERBS = sorted(v for v in M.D["verbs"] if v in M.GV or v in R.verbs)

with gr.Blocks(title="Machina") as demo:
    gr.Markdown(
        "# Machina\n"
        "### Un motore deterministico di ricerca linguistica per il latino\n\n"
        "**La frase non viene predetta. Viene cercata.**\n\n"
        "Nessuna rete neurale. Nessuna probabilità. Nessun generatore casuale. "
        "A parità di stato iniziale, l'output è identico bit per bit.\n\n"
        "*La frase, qui sotto, non è il prodotto. La traccia lo è.*"
    )
    with gr.Row():
        with gr.Column(scale=1):
            verb = gr.Dropdown(VERBS, value="amo" if "amo" in VERBS else VERBS[0],
                               label="Verbo (stato semantico)")
            num = gr.Radio(["sg", "pl"], value="sg", label="Numero")
            adjs = gr.Textbox("bonus, magnus", label="Modificatori ammessi")
            depth = gr.Slider(3, 8, 6, step=1, label="go depth N (parole massime)")
            btn = gr.Button("generate", variant="primary")
        with gr.Column(scale=2):
            out = gr.Textbox(label="Frase latina", lines=1)
            tr = gr.Markdown(label="Traccia")
    with gr.Row():
        vl = gr.Markdown(label="Valenza e restrizioni selettive")
        tv = gr.Markdown(label="Albero sintattico")

    btn.click(run, [verb, num, adjs, depth], [out, tr, vl, tv])

    gr.Markdown(
        "---\n"
        "**Le restrizioni selettive sono a due livelli, entrambi logici:**\n\n"
        "1. **Attestazione** (IT-VaLex): usare le *frequenze* di un corpus come "
        "pesi sarebbe statistica — vietato. Usare l'*attestazione* come predicato "
        "booleano è una relazione logica — ammesso. Machina legge il corpus "
        "**come un dizionario, non come una distribuzione**.\n"
        "2. **Iponimia** (Latin WordNet, 13.868 iperonimie): un filler non "
        "attestato è ammesso se è **iponimo** di uno attestato. L'iponimia è una "
        "relazione d'ordine, non una misura di distanza.\n\n"
        "**Limiti dichiarati:** la funzione di valutazione è monotona crescente "
        "nella lunghezza (il motore tende alla frase più lunga ammissibile, non "
        "alla migliore) — non si presenta in Divinatio, dove la lunghezza della "
        "lacuna è nota; i frame di IT-VaLex sono indotti da parse e contengono "
        "artefatti. Entrambi documentati in `docs/ADR-001.md`.\n\n"
        "Codice **CC0** · dati **non ridistribuiti** (vedi `NOTICE.md`)"
    )

if __name__ == "__main__":
    demo.launch(theme=THEME, css=CSS)
