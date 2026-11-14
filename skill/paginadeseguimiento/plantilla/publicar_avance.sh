#!/usr/bin/env bash
# Publica la página de avance EN VIVO en internet: avance.py (servidor con Server-Sent Events, solo 3 rutas) + túnel Cloudflare.
# Uso: ./publicar_avance.sh [idiomas...]  · Solo reiniciar la página manteniendo el enlace: --pagina [idiomas...]  · Detener: --parar
P="$(cd "$(dirname "$0")" && pwd)"; cd "$P"; export AVANCE_PORT=${AVANCE_PORT:-8765}
matar() { for f in "$@"; do [ -f $f ] && kill $(cat $f) 2>/dev/null; rm -f $f; done; }
case "$1" in
  --parar) matar .avance.pid .tunel.pid; echo "detenido"; exit 0;;
  --pagina) shift; matar .avance.pid; fuser -k $AVANCE_PORT/tcp 2>/dev/null; sleep 1; setsid nohup python3 -I avance.py "$@" > avance.log 2>&1 < /dev/null & echo $! > .avance.pid; cat avance_url.txt 2>/dev/null; exit 0;;
esac
matar .avance.pid .tunel.pid
date +%s > .inicio_avance   # pedido nuevo: la página cuenta solo lo generado desde ahora
nohup python3 -I avance.py "$@" > avance.log 2>&1 & echo $! > .avance.pid
sleep 1
nohup "$HOME/.local/bin/cloudflared" tunnel --no-autoupdate --url http://127.0.0.1:$AVANCE_PORT > tunel.log 2>&1 & echo $! > .tunel.pid
for i in $(seq 30); do U=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" tunel.log | head -1); [ -n "$U" ] && break; sleep 1; done
echo "${U:-ERROR: sin URL, ver tunel.log}"; echo "$U" > avance_url.txt
# portada fija en GitHub Pages (https://allanzuniga-dlg.github.io/monitoreoclaude/): solo se publica la dirección del túnel
[ -n "$U" ] && M="$P/monitoreo/publicar_tunel.sh" && [ -x "$M" ] && "$M" "$U"
