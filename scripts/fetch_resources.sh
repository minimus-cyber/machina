#!/usr/bin/env bash
# Scarica le risorse dalle fonti originali. NULLA e' ridistribuito da questo repo.
# Uso: ./scripts/fetch_resources.sh --profile clean|research
set -euo pipefail
PROFILE="${2:-research}"; mkdir -p data/src; cd data/src
clone() { [ -d "$2" ] || git clone -q --depth 1 "$1" "$2"; echo "  ok $2"; }

echo "== profilo: $PROFILE =="
echo "-- nucleo libero (pubblico dominio / permissivo) --"
clone https://github.com/mk270/whitakers-words.git              whitakers-words
clone https://github.com/GrammaticalFramework/gf-rgl.git        gf-rgl
clone https://github.com/CIRCSE/latinWordnet-revision.git       latin-wordnet
clone https://github.com/UniversalDependencies/UD_Latin-LLCT.git ud-llct

if [ "$PROFILE" = "research" ]; then
  echo "-- estensioni: EREDITANO GPL-3 e CC BY-NC-SA (vedi NOTICE.md) --"
  clone https://github.com/CIRCSE/ITVALEX.git                        itvalex
  clone https://github.com/UniversalDependencies/UD_Latin-PROIEL.git ud-proiel
  clone https://github.com/UniversalDependencies/UD_Latin-Perseus.git ud-perseus
  clone https://github.com/UniversalDependencies/UD_Latin-ITTB.git   ud-ittb
  clone https://github.com/UniversalDependencies/UD_Latin-UDante.git ud-udante
fi
cd ../..
if [ "$PROFILE" = "research" ]; then
  printf 'PROFILO: research\nVINCOLI EREDITATI:\n  - GPL-3 (IT-VaLex): copyleft sui derivati\n  - CC BY-NC-SA (UD Perseus/PROIEL/ITTB/UDante): USO NON COMMERCIALE\nAdatto a ricerca. NON adatto a prodotti commerciali.\n' > data/LICENSE-PROFILE.txt
else
  printf 'PROFILO: clean\nNessun vincolo NC, nessun copyleft sui dati.\nRidistribuibile liberamente. Copertura valenziale ridotta.\n' > data/LICENSE-PROFILE.txt
fi
echo; cat data/LICENSE-PROFILE.txt
