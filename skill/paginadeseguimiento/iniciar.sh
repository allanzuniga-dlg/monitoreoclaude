#!/usr/bin/env bash
# Crea la página de seguimiento de un proyecto y la publica (túnel + enlace fijo de GitHub).
# Uso: iniciar.sh <carpeta_del_proyecto> "Qué se está haciendo"
set -e
SK="$(cd "$(dirname "$0")" && pwd)"; D="${1:?carpeta del proyecto}"; T="${2:-Proyecto}"
mkdir -p "$D/seguimiento"; cd "$D/seguimiento"
[ -f avance.py ] || cp -r "$SK/plantilla/." .
python3 - "$T" <<'P'
import json, sys; c = json.load(open('config.json')); c['titulo'] = sys.argv[1]; json.dump(c, open('config.json', 'w'), ensure_ascii=False, indent=1)
P
python3 -I paso.py --trabajo "$T"
# una sola página en vivo a la vez: el enlace fijo muestra el proyecto que está publicado ahora
fuser -k ${AVANCE_PORT:-8765}/tcp 2>/dev/null || true
./publicar_avance.sh
echo "Enlace fijo: https://allanzuniga-dlg.github.io/monitorinterno/"
