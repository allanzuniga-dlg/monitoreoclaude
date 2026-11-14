#!/usr/bin/env bash
# Publica la dirección del túnel de la página de avance en el repositorio de GitHub Pages «monitoreoclaude»
# (portada fija: https://allanzuniga-dlg.github.io/monitoreoclaude/). Uso: publicar_tunel.sh <url_del_tunel>
# El token se LEE del archivo local de credenciales y nunca se escribe en el repositorio ni en los logs.
U="$1"; [ -n "$U" ] || { echo "uso: $0 <url>"; exit 1; }
TOKF="${GITHUB_TOKEN_FILE:-$HOME/Escritorio/Credenciales/Tokengit.txt}"; REPO="${MONITOREO_REPO:-allanzuniga-dlg/monitoreoclaude}"
[ -r "$TOKF" ] || { echo "MONITOREO: sin archivo de token ($TOKF)"; exit 0; }
T=$(tr -d ' \n\r' < "$TOKF"); API="https://api.github.com/repos/$REPO/contents/tunel.json"
SHA=$(curl -s -H "Authorization: Bearer $T" "$API" | python3 -c "import json,sys;print(json.load(sys.stdin).get('sha',''))" 2>/dev/null)
CONT=$(python3 -c "import json,sys,time,base64;print(base64.b64encode(json.dumps({'url':sys.argv[1],'actualizado':int(time.time())}).encode()).decode())" "$U")
BODY=$(python3 -c "import json,sys;d={'message':'Túnel de avance actualizado','content':sys.argv[1]};sys.argv[2] and d.update(sha=sys.argv[2]);print(json.dumps(d))" "$CONT" "$SHA")
C=$(curl -s -o /dev/null -w "%{http_code}" -X PUT -H "Authorization: Bearer $T" -H "Accept: application/vnd.github+json" "$API" -d "$BODY")
unset T; echo "MONITOREO: tunel.json → $C"
