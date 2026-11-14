# Vista «Mina» de la página de avance (pedido del usuario, 13/11/2026).
# - Cada tarjeta = un OBJETIVO (depósito de cristales al final de su galería). Las TAREAS de la tarjeta (sus pasos) son
#   tramos de la galería, en orden, con su nombre y su % sobre el camino: así se ve por dónde va el pollito.
# - Excavación con lógica: la galería se abre hasta la tarea en curso (las anteriores completas + el % de la actual);
#   una tarea terminada más adelante (fuera de orden) aparece como una cámara ya excavada con ✔.
# - Al 100 % el objetivo va al CARRO MINERO; tocar un objetivo, una gema o el carro muestra el detalle de lo finalizado.
# - CPU > 90 %: el pollito suda. RAM > 90 %: nube de historieta con un cerebro que palpita. Barras animadas de CPU y RAM
#   dentro del mapa. Se inserta en avance.py con aplicar().

CSS = r'''
#minaV{margin-bottom:12px;padding:10px}#minaV #minaS{width:100%;height:auto;display:block;border-radius:10px;user-select:none}
#minaV .obj,#minaV .gema,#minaV .carro,#minaV .tarea{cursor:pointer}#minaV .obj:focus,#minaV .gema:focus,#minaV .tarea:focus{outline:none}
#minaV .obj:hover .cristales,#minaV .obj:focus .cristales{filter:brightness(1.25)}#minaV .gema:hover{filter:brightness(1.3)}
#minaV .rn,#minaV .rp{paint-order:stroke;stroke:#1d120b;stroke-width:3px;stroke-linejoin:round}#minaV .tarea:hover .rocaF{stroke:#fff}#minaV .rocaS{transition:transform .8s ease}#minaV .tarea:hover rect{stroke:#fff}#minaV .sel .aro{stroke:#fff}#minaV .pollo{transition:transform 1.2s ease}
#minaV .pico{transform-box:fill-box;transform-origin:0% 100%;animation:mPico .7s ease-in-out infinite}
#minaV .cuerpoP{animation:mBote .7s ease-in-out infinite}
#minaV .quieto .pico{animation:none;transform:rotate(-20deg)}#minaV .quieto .cuerpoP{animation:none}
#minaV .quieto .tierra{display:none}#minaV .fiesta .cuerpoP{animation:mSalto 1s ease-in-out infinite}
#minaV .tierra circle{animation:mTierra .7s ease-out infinite;opacity:0}
#minaV .tierra circle:nth-child(2){animation-delay:.12s}#minaV .tierra circle:nth-child(3){animation-delay:.24s}#minaV .tierra circle:nth-child(4){animation-delay:.36s}
#minaV .brillo{animation:mBrillo 2.4s ease-in-out infinite}
#minaV .sudor{display:none}#minaV .suda .sudor{display:inline}
#minaV .sudor path{animation:mGota 1.1s ease-in infinite;opacity:0}#minaV .sudor path:nth-child(2){animation-delay:.35s}#minaV .sudor path:nth-child(3){animation-delay:.7s}
#minaV .nube{display:none}#minaV .piensa .nube{display:inline}
#minaV .cerebro{transform-box:fill-box;transform-origin:50% 50%;animation:mLatido .9s ease-in-out infinite}
#minaV .rayas{animation:mRayas 1s linear infinite}
#minaV .ahora rect{stroke:#ffd23f;stroke-width:2}
@keyframes mPico{0%,100%{transform:rotate(-40deg)}45%,55%{transform:rotate(48deg)}}
@keyframes mBote{0%,100%{transform:translateY(0)}50%{transform:translateY(1.5px)}}
@keyframes mSalto{0%,100%{transform:translateY(0)}40%{transform:translateY(-14px)}}
@keyframes mTierra{0%{opacity:1;transform:translate(0,0)}100%{opacity:0;transform:translate(var(--dx),var(--dy))}}
@keyframes mBrillo{0%,100%{opacity:.15}50%{opacity:.9}}
@keyframes mGota{0%{opacity:0;transform:translate(0,0)}15%{opacity:1}100%{opacity:0;transform:translate(var(--gx),16px)}}
@keyframes mLatido{0%,100%{transform:scale(1)}15%{transform:scale(1.16)}30%{transform:scale(.97)}45%{transform:scale(1.1)}}
@keyframes mRayas{to{transform:translateX(16px)}}
@media (prefers-reduced-motion:reduce){#minaV .pico,#minaV .cuerpoP,#minaV .tierra circle,#minaV .brillo,#minaV .sudor path,#minaV .cerebro,#minaV .rayas{animation:none}#minaV .sudor path{opacity:1}}
#minaDet{margin-top:10px;font-size:13px}#minaDet h3{margin:0 0 6px;font-size:15px}#minaDet .vacio{color:var(--mut);margin:4px 2px}
#minaDet .objD{border:1px solid var(--line);border-radius:10px;padding:8px 12px;margin:0 0 8px}
#minaDet .objD h4{margin:0 0 4px;font-size:14px;display:flex;justify-content:space-between;gap:8px}
#minaDet ul{list-style:none;margin:0;padding:0}#minaDet li{padding:2px 0;display:grid;grid-template-columns:22px 1fr auto;gap:6px}
.minaBar{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:0 0 8px}.minaBar b{font-size:14px}
.minaBar button,.mModal button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:8px;padding:5px 12px;font-size:13px;cursor:pointer;font-weight:600}
.minaBar button:hover,.mModal button:hover{border-color:var(--a);color:var(--a)}
.minaMapa{position:relative;min-height:0}
#minaModal{position:absolute;top:0;right:0;bottom:0;left:0;display:flex;align-items:center;justify-content:center;background:#0b0d1f99;border-radius:10px;padding:12px;z-index:5}
#minaModal[hidden]{display:none}
.mModal{background:var(--card);color:var(--ink);border-radius:14px;box-shadow:0 12px 40px #0008;padding:16px 18px;width:min(460px,100%);max-height:100%;overflow:auto}
.mModal .mObj{font-size:12px;color:var(--mut);margin:0 0 2px}.mModal h3{margin:0 0 10px;font-size:17px;line-height:1.3}
.mModal .mPct{display:flex;align-items:center;gap:10px;margin:6px 0 10px}.mModal .mPct b{font-size:26px;min-width:76px}
.mModal .mBar{flex:1;height:14px;border-radius:8px;background:var(--line);overflow:hidden}.mModal .mBar i{display:block;height:100%;background:linear-gradient(90deg,var(--a),var(--ok));transition:width .6s}
.mModal .mEst{display:inline-block;font-size:12px;font-weight:700;padding:2px 10px;border-radius:20px;margin-bottom:8px}
.mModal .e0{background:#8882;color:var(--mut)}.mModal .e1{background:#0071bc22;color:var(--a)}.mModal .e2{background:#00a99d22;color:var(--ok)}
.mModal dl{margin:6px 0 12px;font-size:13px;display:grid;grid-template-columns:auto 1fr;gap:4px 10px}.mModal dt{color:var(--mut)}.mModal dd{margin:0;overflow-wrap:anywhere}
.mModal .mAcc{display:flex;justify-content:flex-end;gap:8px}
.mFsSalir{display:none}#minaV .mFsSalir svg{width:18px;height:18px;display:block}
#minaMapa:fullscreen{display:block;width:100vw;height:100vh;height:100dvh;padding:0;margin:0;background:#4a301e;overflow:hidden}#minaMapa:-webkit-full-screen{display:block;width:100vw;height:100vh;height:100dvh;padding:0;margin:0;background:#4a301e;overflow:hidden}#minaMapa.fsPseudo{display:block;width:100vw;height:100vh;height:100dvh;padding:0;margin:0;background:#4a301e;overflow:hidden}
#minaMapa.fsPseudo{position:fixed;top:0;right:0;bottom:0;left:0;width:100%;height:100%;z-index:9999}
#minaMapa:fullscreen #minaS{width:100%;height:100%;border-radius:0}#minaMapa:-webkit-full-screen #minaS{width:100%;height:100%;border-radius:0}#minaMapa.fsPseudo #minaS{width:100%;height:100%;border-radius:0}
#minaMapa:fullscreen #minaModal{border-radius:0}#minaMapa:-webkit-full-screen #minaModal{border-radius:0}#minaMapa.fsPseudo #minaModal{border-radius:0}
#minaMapa:fullscreen .mFsSalir{display:flex;position:absolute;top:10px;right:10px;z-index:4;width:32px;height:32px;padding:0;border:0;border-radius:50%;align-items:center;justify-content:center;background:#00000040;color:#fff;cursor:pointer;opacity:.5;transition:opacity .2s,background .2s}#minaMapa:-webkit-full-screen .mFsSalir{display:flex;position:absolute;top:10px;right:10px;z-index:4;width:32px;height:32px;padding:0;border:0;border-radius:50%;align-items:center;justify-content:center;background:#00000040;color:#fff;cursor:pointer;opacity:.5;transition:opacity .2s,background .2s}#minaMapa.fsPseudo .mFsSalir{display:flex;position:absolute;top:10px;right:10px;z-index:4;width:32px;height:32px;padding:0;border:0;border-radius:50%;align-items:center;justify-content:center;background:#00000040;color:#fff;cursor:pointer;opacity:.5;transition:opacity .2s,background .2s}
#minaMapa.girado #minaS{position:absolute;top:50%;left:50%;width:100vh;width:100dvh;height:100vw;transform:translate(-50%,-50%) rotate(90deg)}
#minaMapa .mFsSalir:hover,#minaMapa .mFsSalir:focus-visible{opacity:1;background:#00000080;outline:none}
.mModal .mDet ul{list-style:none;margin:0 0 10px;padding:0;font-size:13px}.mModal .mDet li{display:grid;grid-template-columns:22px 1fr auto;gap:6px;padding:2px 0}
.mModal .mDet li small{grid-column:2/4;color:var(--mut)}.mModal .mDet h4{margin:8px 0 4px;font-size:14px;display:flex;justify-content:space-between}
.frente{display:none}.atiende .frente{display:inline}.atiende .lado{display:none}
#minaV .globo{cursor:pointer;animation:mGlobo 1.6s ease-in-out infinite}#minaV .globo:hover rect{fill:#fff8d6}
#minaV .saludo{transform-box:fill-box;transform-origin:0% 100%;animation:mSaludo .9s ease-in-out infinite}
#minaV .atiende .cuerpoF{animation:mSalto 1.4s ease-in-out infinite}
@keyframes mGlobo{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}
@keyframes mSaludo{0%,100%{transform:rotate(0)}50%{transform:rotate(-25deg)}}
.mModal .mAccion{border-left:4px solid #ff8a00;background:#ff8a0014;border-radius:8px;padding:8px 12px;margin:0 0 8px}.mModal .mAccion b{display:block;font-size:15px}
.mModal .mAccion p{margin:4px 0 0;font-size:13.5px}.mModal .mAccion small{color:var(--mut);font-size:11.5px}
#minaV .brazoQuieto{display:none}#minaV .quieto .brazoAnim{display:none}#minaV .quieto .brazoQuieto{display:inline}
#minaDet li small{grid-column:2/4;color:var(--mut);margin-top:-2px}#minaDet .meta{color:var(--mut);font-size:12px;margin:2px 0 6px}
'''

HTML = r'''<section id="minaV" class="card fija hide"><div class="minaBar"><b>⛏ Mina del avance</b><button id="minaFS" type="button" aria-pressed="false">⛶ Pantalla completa</button></div><div class="minaMapa" id="minaMapa"><button id="minaFSsalir" class="mFsSalir" type="button" title="Salir de pantalla completa" aria-label="Salir de pantalla completa"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5"/></svg></button><svg id="minaS" role="img" aria-label="Mina del avance"></svg><div id="minaModal" hidden role="dialog" aria-modal="true" aria-labelledby="mTit"><div class="mModal" id="mCont"></div></div></div><div id="minaDet"><p class="vacio">Toque un objetivo, una tarea o el carro minero para ver el detalle.</p></div></section>'''

JS = r'''
// ---- vista «Mina»: el pollito cava tarea por tarea hacia cada objetivo; lo terminado va al carro
const MINA = {key: '', sel: null, E: null};
const COLG = ['#3fb6ff', '#ff5d8f', '#7ee081', '#ffb547', '#b18cff', '#4fd1c5', '#ff7a45', '#f5e663'];
const finM = e => e.ok && (e.drive || e.tarea) || e.pct >= 100;
const corto = (s, n) => s.length > n ? s.slice(0, n - 1) + '…' : s;
const nomTarea = s => s.replace(/:\s.*$/, '').trim();   // «Voz: 7 de 34 frases» → «Voz»; «0:20 · …» queda igual
const sv = (tag, at, padre) => { const el = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const k in at) el.setAttribute(k, at[k]); if (padre) padre.appendChild(el); return el; };
let NIVEL = 170; const X0 = 110, XF = 840;    // pique en X0; cada galería llega al objetivo en XF
// la escena llena TODA la pantalla disponible (14/11: «verifica que siempre tome toda la pantalla»): el alto del mapa es el de la
// ventana y la separación entre galerías se estira para ocupar ese alto (150–320), sin deformar ni cortar nada
function minaCaja() {
  const m = $('#minaMapa'); if (!m) return {w: 1000, h: 600};
  if (minaEnFS()) { const r = m.getBoundingClientRect(), gir = m.classList.contains('girado'); return gir ? {w: r.height, h: r.width} : {w: r.width, h: r.height}; }
  const w = Math.max(320, m.getBoundingClientRect().width || m.parentElement.clientWidth || 1000);
  return {w, h: Math.max(340, innerHeight - 64)};
}
// alto de la escena: 200 (cielo + primera galería) + una separación por galería extra + 150 de tierra para los rótulos de abajo
const minaAlto = n => 200 + (Math.max(n, 1) - 1) * NIVEL + 150;
// separación fija entre galerías (14/11: estirarla dejaba los objetivos muy distantes y espacio sobrante arriba y abajo);
// en pantalla completa se permite un poco más (hasta 230) para usar el alto sin separarlos de más
function minaNivel(n) { if (n < 2 || !minaEnFS()) return 170; const c = minaCaja(), Hob = 1000 * c.h / c.w; return Math.round(Math.max(150, Math.min(230, (Hob - 350) / (n - 1)))); }
const minaClave = E => E.idiomas.map(e => e.L + ':' + e.pasos.length).join('|') + '#' + minaNivel(Math.max(E.idiomas.length, 1));
// los rótulos nunca se cortan ni llevan «…»: se reparten en líneas por palabras
function minaLineas(t, n) { const L = []; let a = ''; String(t).split(/\s+/).forEach(p => { if (a && (a + ' ' + p).length > n) { L.push(a); a = p; } else a = a ? a + ' ' + p : p; }); if (a) L.push(a); return L; }
function minaTexto(el, L, x, y0, dy) { el.textContent = ''; L.forEach((l, i) => { const t = sv('tspan', {x, y: y0 + i * dy}, el); t.textContent = l; }); }
// excavación con lógica: completas las tareas anteriores a la que está en curso + el % de esa
function cavado(e) {
  const P = e.pasos, k = P.length; if (!k) return {f: e.pct / 100, act: -1};
  if (finM(e)) return {f: 1, act: -1};
  let act = P.findIndex(p => p[1] > 0 && p[1] < 100);
  if (act < 0) act = P.findIndex(p => p[1] < 100);
  if (act < 0) return {f: 1, act: -1};
  return {f: (act + P[act][1] / 100) / k, act};
}
function minaArmar(E) {
  const s = $('#minaS'); s.innerHTML = ''; const n = E.idiomas.length; NIVEL = minaNivel(Math.max(n, 1)); const H = minaAlto(n);
  s.setAttribute('viewBox', `0 0 1000 ${H}`); MINA.H = H;
  sv('defs', {}, s).innerHTML = `<linearGradient id="mCielo" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8fd3ff"/><stop offset="1" stop-color="#d9f1ff"/></linearGradient>
    <linearGradient id="mTierraG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9a6b43"/><stop offset=".35" stop-color="#7b5233"/><stop offset="1" stop-color="#4a301e"/></linearGradient>
    <radialGradient id="mLuz"><stop offset="0" stop-color="#fff3a8" stop-opacity=".55"/><stop offset="1" stop-color="#fff3a8" stop-opacity="0"/></radialGradient>
    <pattern id="mRay" width="16" height="16" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="16" fill="#ffffff33"/></pattern>`;
  sv('rect', {x: -3000, y: -3000, width: 7000, height: 3112, fill: '#d9f1ff'}, s); sv('rect', {x: -3000, y: 0, width: 7000, height: 112, fill: 'url(#mCielo)'}, s);
  sv('circle', {cx: 960, cy: 30, r: 18, fill: '#ffe066'}, s);
  sv('rect', {x: -3000, y: 110, width: 7000, height: H - 110, fill: 'url(#mTierraG)'}, s); sv('rect', {x: -3000, y: H - 1, width: 7000, height: 3000, fill: '#4a301e'}, s);
  sv('rect', {x: -3000, y: 106, width: 7000, height: 8, fill: '#5fb04a'}, s);
  for (let k = 0; k < 4; k++) { const y = 170 + k * (H - 170) / 4; sv('path', {d: `M0 ${y} Q 250 ${y - 10} 500 ${y + 8} T 1000 ${y - 2}`, stroke: '#00000022', 'stroke-width': 3, fill: 'none'}, s); }
  let sem = 7; const rnd = () => (sem = (sem * 9301 + 49297) % 233280) / 233280;
  for (let k = 0; k < 50; k++) sv('ellipse', {cx: rnd() * 1000, cy: 125 + rnd() * (H - 135), rx: 3 + rnd() * 9, ry: 2 + rnd() * 6, fill: rnd() > .5 ? '#5c3d27' : '#a37a55', opacity: .5}, s);
  sv('path', {d: 'M78 112 L78 78 Q110 52 142 78 L142 112 Z', fill: '#24170f', stroke: '#8a5a2b', 'stroke-width': 6}, s);
  sv('rect', {x: 70, y: 70, width: 80, height: 9, rx: 2, fill: '#8a5a2b'}, s);
  // avance total: etiqueta discreta arriba a la izquierda, con el estilo del panel de CPU / RAM
  const pt = sv('g', {transform: 'translate(14 10)'}, s);
  sv('rect', {x: 0, y: 0, width: 168, height: 32, rx: 8, fill: '#0d1117c4'}, pt);
  sv('text', {x: 10, y: 15, 'font-size': 10, 'font-weight': 700, fill: '#8b949e', 'letter-spacing': '.06em', 'font-family': 'ui-monospace,monospace'}, pt).textContent = 'AVANCE TOTAL';
  const tv = sv('text', {x: 158, y: 17, 'text-anchor': 'end', 'font-size': 14, 'font-weight': 800, fill: '#ffd23f', 'font-family': 'ui-monospace,monospace'}, pt);
  sv('rect', {x: 10, y: 22, width: 148, height: 4, rx: 2, fill: '#21262d'}, pt);
  const cr = sv('rect', {x: 10, y: 22, width: 0, height: 4, rx: 2, fill: '#ffb000'}, pt);
  MINA.tot = {tv, cr};
  for (let x = 180; x <= 560; x += 22) sv('rect', {x, y: 104, width: 12, height: 5, fill: '#6b4a2b'}, s);
  sv('line', {x1: 170, y1: 104, x2: 570, y2: 104, stroke: '#9aa3ad', 'stroke-width': 3}, s);
  // medidores de CPU y RAM (barras animadas)
  const med = sv('g', {transform: 'translate(640 18)'}, s); MINA.med = {};
  sv('rect', {x: -10, y: -8, width: 300, height: 80, rx: 10, fill: '#0d1117d9'}, med);
  [['cpu', 'CPU', 14], ['ram', 'RAM', 46]].forEach(([k, t, y]) => {
    sv('text', {x: 0, y: y + 12, 'font-size': 13, 'font-weight': 700, fill: '#c9d1d9', 'font-family': 'ui-monospace,monospace'}, med).textContent = t;
    sv('rect', {x: 40, y, width: 180, height: 16, rx: 8, fill: '#21262d'}, med);
    const cl = sv('clipPath', {id: 'mClip' + k}, med), cr = sv('rect', {x: 40, y, width: 0, height: 16, rx: 8}, cl);
    const g = sv('g', {'clip-path': `url(#mClip${k})`}, med), bar = sv('rect', {x: 40, y, width: 180, height: 16, fill: '#3fb950'}, g);
    sv('rect', {x: 24, y, width: 220, height: 16, fill: 'url(#mRay)', class: 'rayas'}, g);
    const v = sv('text', {x: 228, y: y + 13, 'font-size': 12.5, fill: '#c9d1d9', 'font-family': 'ui-monospace,monospace'}, med);
    MINA.med[k] = {cr, bar, v};
  });
  const capT = sv('g', {}, s), capW = sv('g', {}, s), capO = sv('g', {}, s);
  const fondoP = 200 + (n - 1) * NIVEL + 10;
  sv('path', {d: `M${X0} 112 L${X0} ${fondoP}`, stroke: '#1d120b', 'stroke-width': 34, 'stroke-linecap': 'round'}, capT);
  sv('path', {d: `M${X0} 112 L${X0} ${fondoP}`, stroke: '#3a271a', 'stroke-width': 24, 'stroke-linecap': 'round'}, capT);
  for (let y = 130; y < fondoP; y += 26) sv('line', {x1: X0 - 12, y1: y, x2: X0 + 12, y2: y, stroke: '#8a5a2b', 'stroke-width': 3}, capT);
  MINA.gal = []; MINA.objs = [];
  E.idiomas.forEach((e, i) => {
    const y = 200 + i * NIVEL, col = COLG[i % COLG.length], dd = `M${X0} ${y} C ${X0 + 240} ${y + 22}, ${XF - 300} ${y - 22}, ${XF} ${y}`;
    sv('path', {d: dd, stroke: '#00000040', 'stroke-width': 3, 'stroke-dasharray': '5 9', fill: 'none'}, capT);
    const fondo = sv('path', {d: dd, stroke: '#1d120b', 'stroke-width': 30, 'stroke-linecap': 'round', fill: 'none', pathLength: 1000, 'stroke-dasharray': '0 1000'}, capT);
    const luz = sv('path', {d: dd, stroke: '#3a271a', 'stroke-width': 20, 'stroke-linecap': 'round', fill: 'none', pathLength: 1000, 'stroke-dasharray': '0 1000'}, capT);
    const L = fondo.getTotalLength(), k = Math.max(1, e.pasos.length), pt = t => fondo.getPointAtLength(L * t);
    // tareas: un tramo por paso; poste al final de cada tramo y rótulo (arriba / abajo, alternado) en el medio
    const tareas = e.pasos.map((p, j) => {
      const fin = pt((j + 1) / k), mid = pt((j + .5) / k), arriba = j % 2 === 0, g = sv('g', {class: 'tarea', tabindex: 0, role: 'button'}, capW);
      g.dataset.l = e.L; g.dataset.j = j;
      const cam = sv('ellipse', {cx: mid.x, cy: mid.y, rx: 16, ry: 11, fill: '#3a271a', stroke: '#1d120b', 'stroke-width': 3, class: 'hide'}, g);
      if (j < k - 1) { sv('line', {x1: fin.x, y1: fin.y - 17, x2: fin.x, y2: fin.y + 17, stroke: '#8a5a2b', 'stroke-width': 4}, g); sv('line', {x1: fin.x - 8, y1: fin.y - 17, x2: fin.x + 8, y2: fin.y - 17, stroke: '#8a5a2b', 'stroke-width': 4}, g); }
      const ty = arriba ? mid.y - 50 : mid.y + 22, w = Math.min(Math.max(64, 860 / k - 10), 2 * (XF - 14 - mid.x)), et = sv('g', {}, g);   // no se monta sobre el rótulo del objetivo
      sv('line', {x1: mid.x, y1: arriba ? ty + 30 : ty, x2: mid.x, y2: arriba ? mid.y - 14 : mid.y + 14, stroke: '#ffffff55', 'stroke-width': 1.5, 'stroke-dasharray': '2 3'}, et);
      const r = sv('rect', {x: mid.x - w / 2, y: ty, width: w, height: 30, rx: 7, fill: '#000000a0'}, et);
      const tn = sv('text', {x: mid.x, y: ty + 12, 'text-anchor': 'middle', 'font-size': 10.5, fill: '#fff'}, et);
      const tp = sv('text', {x: mid.x, y: ty + 25, 'text-anchor': 'middle', 'font-size': 11, 'font-weight': 800, fill: col}, et);
      sv('rect', {x: mid.x - w / 2 + 4, y: ty + 27, width: w - 8, height: 2, fill: '#ffffff30'}, et);
      const tb = sv('rect', {x: mid.x - w / 2 + 4, y: ty + 27, width: 0, height: 2, fill: col}, et);
      const tt = sv('title', {}, g);
      // tarea sin terminar = roca en el camino que se achica con el avance (0 % entera); al 100 % se va y queda su tarjeta (14/11)
      const ro = sv('g', {transform: `translate(${mid.x} ${mid.y})`}, g), rs = sv('g', {class: 'rocaS'}, ro);
      sv('path', {class: 'rocaF', d: 'M-21 8 L-24 -3 L-15 -16 L-2 -21 L12 -17 L22 -6 L23 7 Z', fill: '#7d6a5c', stroke: '#3b2f27', 'stroke-width': 2.2, 'stroke-linejoin': 'round'}, rs);
      sv('path', {d: 'M-15 -14 L-3 -18 L8 -15 L-2 -9 Z', fill: '#a08b7a', opacity: .9}, rs);
      sv('path', {d: 'M-21 8 L23 7 L19 1 L-18 2 Z', fill: '#5b4a3e', opacity: .8}, rs);
      const rp = sv('text', {class: 'rp', x: 0, y: 2, 'text-anchor': 'middle', 'font-size': 10.5, 'font-weight': 800, fill: '#fff'}, ro);
      const rn = sv('text', {class: 'rn', 'text-anchor': 'middle', 'font-size': 10, 'font-weight': 600, fill: '#fff'}, g);
      return {g, cam, tn, tp, tb, tt, w, et, arriba, r, ty, mx: mid.x, my: mid.y, ro, rs, rp, rn};
    });
    MINA.gal.push({fondo, luz, L, tareas, y});
    // objetivo al final de la galería
    const g = sv('g', {class: 'obj', tabindex: 0, role: 'button', transform: `translate(${XF + 70} ${y})`}, capO); g.dataset.l = e.L;
    sv('circle', {r: 44, fill: 'url(#mLuz)', class: 'brillo'}, g);
    const cr = sv('g', {class: 'cristales'}, g);
    [[-14, 8, 16, 34], [4, 10, 20, 44], [20, 8, 14, 28]].forEach(([x, yy, w, h]) => sv('path', {d: `M${x} ${yy} L${x - w / 2} ${yy - h * .65} L${x} ${yy - h} L${x + w / 2} ${yy - h * .65} Z`, fill: col, stroke: '#ffffffaa', 'stroke-width': 1.5}, cr));
    const hueco = sv('g', {class: 'hide'}, g);   // objetivo alcanzado: el porcentaje logrado en el lugar de los cristales
    sv('circle', {r: 28, fill: '#1d120b', stroke: col, 'stroke-width': 2}, hueco);
    const logrado = sv('text', {x: 0, y: 3, 'text-anchor': 'middle', 'font-size': 15, 'font-weight': 800, fill: col}, hueco);
    sv('text', {x: 0, y: 14, 'text-anchor': 'middle', 'font-size': 6.2, 'font-weight': 700, fill: '#ffffffb0'}, hueco).textContent = 'LOGRADO';
    sv('circle', {r: 36, fill: 'none', stroke: '#00000055', 'stroke-width': 7}, g);
    const aro = sv('circle', {r: 36, fill: 'none', stroke: col, 'stroke-width': 7, 'stroke-linecap': 'round', pathLength: 100, 'stroke-dasharray': '0 100', transform: 'rotate(-90)', class: 'aro'}, g);
    const caja = sv('rect', {x: -66, y: -84, width: 132, height: 40, rx: 9, fill: '#000000b0'}, g);
    const nom = sv('text', {x: 0, y: -67, 'text-anchor': 'middle', 'font-size': 12.5, fill: '#fff', 'font-weight': 700}, g);
    const pct = sv('text', {x: 0, y: -51, 'text-anchor': 'middle', 'font-size': 13, fill: col, 'font-weight': 800}, g);
    const tt = sv('title', {}, g);
    MINA.objs.push({g, cr, hueco, logrado, aro, nom, pct, tt, col, caja});
  });
  const cg = sv('g', {class: 'carro', tabindex: 0, role: 'button', transform: 'translate(430 96)'}, s);
  MINA.gemas = sv('g', {}, cg);
  sv('path', {d: 'M-62 -50 L62 -50 L52 -6 L-52 -6 Z', fill: '#6b7280', stroke: '#374151', 'stroke-width': 3}, cg);
  sv('rect', {x: -66, y: -54, width: 132, height: 8, rx: 3, fill: '#4b5563'}, cg);
  [-30, 30].forEach(x => { sv('circle', {cx: x, cy: 0, r: 9, fill: '#1f2937'}, cg); sv('circle', {cx: x, cy: 0, r: 3, fill: '#9ca3af'}, cg); });
  MINA.carroT = sv('text', {x: 0, y: -24, 'text-anchor': 'middle', 'font-size': 13, fill: '#fff', 'font-weight': 700}, cg);
  // pollito minero (origen en las patas, mirando a la derecha); la nube y el sudor no se espejan
  MINA.extras = sv('g', {class: 'extras'}, s);   // pollitos de las tareas que se hacen al mismo tiempo
  const po = sv('g', {class: 'pollo'}, s); MINA.pollo = po; const pv = sv('g', {}, po); MINA.giro = pv;
  pv.innerHTML = `<ellipse cx="0" cy="2" rx="20" ry="4" fill="#00000055"/><g class="lado">
    <polygon points="24,-58 95,-80 95,-34" fill="#fff3a8" opacity=".12"/>
    <g class="cuerpoP">
      <path d="M-6 0 l-4 6 M-6 0 l0 7 M-6 0 l4 6 M8 0 l-4 6 M8 0 l0 7 M8 0 l4 6" stroke="#f59e0b" stroke-width="2.6" stroke-linecap="round"/>
      <ellipse cx="0" cy="-20" rx="21" ry="19" fill="#ffd23f"/>
      <circle cx="6" cy="-44" r="15" fill="#ffd23f"/>
      <circle cx="12" cy="-46" r="2.6" fill="#2b2118"/><circle cx="12.8" cy="-46.8" r=".8" fill="#fff"/>
      <ellipse cx="9" cy="-38" rx="4" ry="2.4" fill="#ff9e7a" opacity=".75"/>
      <path d="M20 -45 l9 3 l-9 3 z" fill="#f59e0b"/>
      <path d="M-10 -51 A16 14 0 0 1 23 -51 Z" fill="#ffb000" stroke="#c77c00" stroke-width="1.5"/>
      <rect x="-13" y="-53" width="40" height="5" rx="2.5" fill="#e09a00"/>
      <circle cx="22" cy="-57" r="4.5" fill="#fff6b0" stroke="#c77c00" stroke-width="1.2"/>
      <g class="sudor"><path d="M-8 -44 q-3 5 0 7 q3 -2 0 -7 z" fill="#7cc8ff" style="--gx:-6px"/><path d="M-4 -52 q-3 5 0 7 q3 -2 0 -7 z" fill="#7cc8ff" style="--gx:-10px"/><path d="M-11 -36 q-3 5 0 7 q3 -2 0 -7 z" fill="#7cc8ff" style="--gx:-4px"/></g>
      <!-- brazo: el ala sostiene el pico y gira desde el hombro (SMIL: anda también en Safari 12) -->
      <g class="brazoAnim"><g><line x1="13" y1="-18" x2="30" y2="-60" stroke="#8a5a2b" stroke-width="4" stroke-linecap="round"/>
          <path d="M16 -64 Q32 -69 47 -53 L43 -50 Q31 -61 19 -59 Z" fill="#9aa3ad" stroke="#5b636b" stroke-width="1.2"/>
          <path d="M-4 -33 Q8 -40 19 -33 Q23 -29 19 -25 Q8 -21 -4 -25 Z" fill="#fbcb30" stroke="#e8b52a" stroke-width=".8" stroke-opacity=".7"/>
          <ellipse cx="18" cy="-29" rx="3.2" ry="4" fill="#fbcb30" stroke="#e8b52a" stroke-width=".8" stroke-opacity=".7"/>
        <animateTransform attributeName="transform" type="rotate" values="-38 0 -29;42 0 -29;42 0 -29;-38 0 -29" keyTimes="0;0.42;0.55;1" dur="0.7s" repeatCount="indefinite"/></g></g>
      <g class="brazoQuieto" transform="rotate(-25 0 -29)"><line x1="13" y1="-18" x2="30" y2="-60" stroke="#8a5a2b" stroke-width="4" stroke-linecap="round"/>
          <path d="M16 -64 Q32 -69 47 -53 L43 -50 Q31 -61 19 -59 Z" fill="#9aa3ad" stroke="#5b636b" stroke-width="1.2"/>
          <path d="M-4 -33 Q8 -40 19 -33 Q23 -29 19 -25 Q8 -21 -4 -25 Z" fill="#fbcb30" stroke="#e8b52a" stroke-width=".8" stroke-opacity=".7"/>
          <ellipse cx="18" cy="-29" rx="3.2" ry="4" fill="#fbcb30" stroke="#e8b52a" stroke-width=".8" stroke-opacity=".7"/></g>
    </g>
    <g class="tierra"><circle cx="46" cy="-18" r="3" fill="#a37a55" style="--dx:18px;--dy:-14px"/><circle cx="46" cy="-14" r="2.5" fill="#7b5233" style="--dx:22px;--dy:-4px"/>
      <circle cx="44" cy="-20" r="2" fill="#c49a6c" style="--dx:12px;--dy:-22px"/><circle cx="48" cy="-12" r="2.2" fill="#5c3d27" style="--dx:26px;--dy:6px"/></g></g>
    <g class="frente"><g class="cuerpoF">
      <path d="M-8 0 l-4 6 M-8 0 l0 7 M-8 0 l4 6 M8 0 l-4 6 M8 0 l0 7 M8 0 l4 6" stroke="#f59e0b" stroke-width="2.6" stroke-linecap="round"/>
      <ellipse cx="0" cy="-20" rx="22" ry="19" fill="#ffd23f"/>
      <path d="M-20 -24 q-12 -2 -14 -14 q10 0 16 8 z" fill="#f2bf1c"/><g class="saludo"><path d="M20 -24 q12 -6 12 -20 q-12 2 -16 12 z" fill="#f2bf1c"/></g>
      <circle cx="0" cy="-46" r="16" fill="#ffd23f"/>
      <circle cx="-6" cy="-47" r="2.8" fill="#2b2118"/><circle cx="6" cy="-47" r="2.8" fill="#2b2118"/><circle cx="-5.2" cy="-48" r=".9" fill="#fff"/><circle cx="6.8" cy="-48" r=".9" fill="#fff"/>
      <ellipse cx="-11" cy="-40" rx="4" ry="2.4" fill="#ff9e7a" opacity=".75"/><ellipse cx="11" cy="-40" rx="4" ry="2.4" fill="#ff9e7a" opacity=".75"/>
      <path d="M-5 -42 l10 0 l-5 7 z" fill="#f59e0b"/>
      <path d="M-17 -54 A17 15 0 0 1 17 -54 Z" fill="#ffb000" stroke="#c77c00" stroke-width="1.5"/><rect x="-20" y="-56" width="40" height="5" rx="2.5" fill="#e09a00"/>
      <circle cx="0" cy="-62" r="4.5" fill="#fff6b0" stroke="#c77c00" stroke-width="1.2"/>
      <g transform="translate(-30 -6) rotate(-20)"><line x1="0" y1="0" x2="0" y2="-30" stroke="#8a5a2b" stroke-width="3.5" stroke-linecap="round"/><path d="M-12 -32 Q0 -38 12 -32 L10 -28 Q0 -33 -10 -28 Z" fill="#9aa3ad"/></g>
    </g></g>`;
  MINA.globo = sv('g', {class: 'globo', role: 'button', tabindex: 0}, po);
  const nb = sv('g', {class: 'nube'}, po);
  nb.innerHTML = `<circle cx="-4" cy="-66" r="3.5" fill="#fff" stroke="#333" stroke-width="1.5"/><circle cx="-10" cy="-78" r="5.5" fill="#fff" stroke="#333" stroke-width="1.5"/>
    <path d="M-52 -96 q-10 -22 12 -26 q6 -18 28 -12 q14 -14 30 0 q22 -4 20 18 q14 12 -4 24 q-4 16 -24 10 q-14 12 -30 0 q-26 6 -32 -14 z" fill="#fff" stroke="#333" stroke-width="2"/>
    <g class="cerebro"><path d="M-32 -110 q-2 -14 12 -16 q4 -8 14 -4 q10 -6 16 4 q12 2 10 14 q6 10 -4 16 q-2 10 -14 8 q-8 6 -16 0 q-14 2 -16 -10 q-8 -6 -2 -12 z" fill="#ff8fb1" stroke="#c2185b" stroke-width="1.8"/>
      <path d="M-22 -118 q6 4 2 10 M-8 -122 q-2 8 6 10 q6 2 4 10 M6 -114 q-6 6 0 12 M-24 -100 q8 -2 12 4 M2 -96 q4 -6 10 -2" stroke="#c2185b" stroke-width="1.5" fill="none" stroke-linecap="round"/></g>
    <text x="-2" y="-78" text-anchor="middle" font-size="9.5" font-weight="700" fill="#c2185b">RAM</text>`;
  MINA.key = minaClave(E);
}
function minaGlobo(acc, x, y) {
  const g = MINA.globo; if (!g) return;
  const clave = acc ? JSON.stringify(acc.map(a => a[1])) + '|' + Math.round(x / 40) + '|' + Math.round(y / 40) : '';
  if (clave === MINA.globoK) return; MINA.globoK = clave; g.innerHTML = '';
  if (!acc) return;
  const txt = acc.map(a => (acc.length > 1 ? '• ' : '') + a[1]).join(' ');
  const lin = [acc.length > 1 ? `¡Necesito su ayuda! (${acc.length})` : '¡Necesito su ayuda!']; let l = '';
  txt.split(' ').forEach(w => { if ((l + ' ' + w).trim().length > 30) { lin.push(l.trim()); l = w; } else l += ' ' + w; }); if (l.trim()) lin.push(l.trim());
  const L = lin.slice(0, 6); if (lin.length > 6) L[5] = L[5].replace(/.{0,2}$/, '…'); L.push('(toque para ver cómo)');
  const w = Math.max(...L.map(t => t.length)) * 7.2 + 26, h = L.length * 17 + 20, base = -84;
  // arriba de la cabeza; si ahí taparía los paneles del cielo (CPU/RAM, avance total), va al costado del pollito
  const arriba = y + base - h > 120, lado = x + 40 + w < 992 ? 1 : -1;
  const bx = arriba ? Math.max(8 - x, Math.min(992 - x - w, -w / 2)) : (lado > 0 ? 40 : -40 - w), by = arriba ? base - h : Math.max(122 - y, -60 - h / 2);
  sv('rect', {x: bx, y: by, width: w, height: h, rx: 12, fill: '#fff', stroke: '#2b2118', 'stroke-width': 2}, g);
  if (arriba) {
    sv('path', {d: `M${Math.max(bx + 14, -10)} ${base - 1} L0 -68 L${Math.min(bx + w - 14, 10)} ${base - 1} Z`, fill: '#fff', stroke: '#2b2118', 'stroke-width': 2, 'stroke-linejoin': 'round'}, g);
    sv('rect', {x: Math.max(bx + 12, -12), y: base - 4, width: 26, height: 5, fill: '#fff'}, g);
  } else {
    const ex = lado > 0 ? bx + 1 : bx + w - 1, ty = Math.min(Math.max(-52, by + 12), by + h - 22);
    sv('path', {d: `M${ex} ${ty} L${lado * 18} -50 L${ex} ${ty + 14} Z`, fill: '#fff', stroke: '#2b2118', 'stroke-width': 2, 'stroke-linejoin': 'round'}, g);
    sv('rect', {x: ex - 3, y: ty + 1, width: 6, height: 12, fill: '#fff'}, g);
  }
  L.forEach((t, i) => sv('text', {x: bx + 13, y: by + 22 + i * 17, 'font-size': i === L.length - 1 ? 11 : 13, 'font-weight': i === 0 ? 800 : 500, fill: i === 0 ? '#c65f00' : i === L.length - 1 ? '#7a6a55' : '#2b2118'}, g).textContent = t);
  sv('title', {}, g).textContent = acc.map(a => a[1] + (a[2] ? ' — ' + a[2] : '')).join('\n');
}
function minaDetalle() {
  const E = MINA.E; if (!E) return; const box = $('#minaDet');
  const uno = e => `<div class="objD"><h4><span>${finM(e) ? '✔' : '⛏'} ${esc(e.nombre)}</span><span>${e.pct}%</span></h4>
    ${e.archivo ? `<p class="meta">${esc(e.archivo)}${e.dur ? ' · ' + e.dur + ' s' : ''}</p>` : ''}
    ${e.drive ? `<a class="drv" target="_blank" rel="noopener" href="${esc(e.drive)}">▶ Ver en Drive</a>` : ''}
    <ul>${e.pasos.map(p => `<li><span>${p[1] >= 100 ? '✅' : p[1] > 0 ? '⛏' : '⬜'}</span><span>${esc(p[0])}</span><b>${p[1]}%</b>${p[2] ? `<small>${esc(p[2])}</small>` : ''}</li>`).join('')}</ul></div>`;
  if (MINA.sel === '__carro') {
    const f = E.idiomas.filter(finM);
    box.innerHTML = `<h3>🛒 En el carro minero: ${f.length} objetivo(s) finalizado(s)</h3>` + (f.length ? f.map(uno).join('') : '<p class="vacio">Todavía no hay objetivos al 100 %.</p>');
  } else { const e = E.idiomas.find(x => x.L === MINA.sel);
    box.innerHTML = e ? `<h3>${finM(e) ? '🛒 Finalizado' : '⛏ En la mina'}</h3>` + uno(e) : '<p class="vacio">Toque un objetivo, una tarea o el carro minero para ver el detalle.</p>'; }
}
function minaMedidor(k, p, txt) {
  const m = MINA.med[k], c = p > 90 ? '#f85149' : p > 70 ? '#d29922' : '#3fb950';
  m.cr.setAttribute('width', 180 * Math.max(0, Math.min(100, p)) / 100); m.bar.setAttribute('fill', c); m.v.textContent = txt;
}
function mina(E) {
  MINA.E = E; if (MINA.key !== minaClave(E)) minaArmar(E);
  MINA.tot.tv.textContent = E.total + '%'; MINA.tot.cr.setAttribute('width', 148 * Math.max(0, Math.min(100, E.total)) / 100);
  const S = E.sis || {}, cpu = S.total || 0, ram = S.mem ? 100 * S.mem[0] / S.mem[1] : 0;
  minaMedidor('cpu', cpu, cpu.toFixed(0) + '%'); minaMedidor('ram', ram, ram.toFixed(0) + '%');
  const fins = [];
  E.idiomas.forEach((e, i) => {
    const o = MINA.objs[i], G = MINA.gal[i], f = finM(e), c = cavado(e), largo = Math.round(1000 * c.f);
    G.fondo.setAttribute('stroke-dasharray', `${largo} 1000`); G.luz.setAttribute('stroke-dasharray', `${largo} 1000`);
    e.pasos.forEach((p, j) => { const T = G.tareas[j]; if (!T) return; const v = f ? 100 : p[1];
      const Ln = minaLineas(nomTarea(p[0]), Math.max(8, Math.floor((T.w - 8) / 5.6))), ex = 12 * (Ln.length - 1), y0 = T.arriba ? T.ty - ex : T.ty;
      minaTexto(T.tn, Ln, T.mx, y0 + 12, 12); T.ex = ex; T.r.setAttribute('y', y0); T.r.setAttribute('height', 30 + ex);
      T.tp.setAttribute('y', y0 + 25 + ex); T.tb.setAttribute('y', y0 + 27 + ex); T.tb.previousElementSibling.setAttribute('y', y0 + 27 + ex);
      T.tp.textContent = (v >= 100 ? '✔ ' : j === c.act ? '⛏ ' : '') + v + '%';
      T.tb.setAttribute('width', (T.w - 8) * v / 100);
      T.cam.classList.toggle('hide', !(v >= 100 && c.act >= 0 && j > c.act));   // terminada fuera de orden: cámara ya excavada
      T.g.classList.toggle('ahora', j === c.act); T.et.setAttribute('transform', j === c.act && T.arriba ? `translate(0 ${72 + (T.ex || 0)})` : '');   // el rótulo de la tarea en curso va debajo: arriba está el pollito
      T.tt.textContent = `${p[0]}: ${v}%${p[2] ? ' · ' + p[2] : ''}`;
      const roca = v < 100; T.et.style.display = roca ? 'none' : ''; T.ro.style.display = T.rn.style.display = roca ? '' : 'none';
      // la roca de la tarea en curso va justo delante del pollito, para que no la tape
      { const q = j === c.act ? G.fondo.getPointAtLength(Math.min(G.L, G.L * c.f + 30)) : {x: T.mx, y: T.my}; T.ro.setAttribute('transform', `translate(${q.x} ${q.y})`); }
      if (roca) { T.rs.setAttribute('transform', `scale(${(1 - .7 * v / 100).toFixed(3)})`); T.rp.textContent = v + '%';
        const Lr = minaLineas(nomTarea(p[0]), Math.max(8, Math.floor((T.w - 4) / 5.4))), ar = T.arriba && !(j === c.act);
        minaTexto(T.rn, Lr, T.mx, ar ? T.my - 28 - 11 * (Lr.length - 1) : T.my + 34, 11); } });
    o.aro.setAttribute('stroke-dasharray', `${f ? 100 : e.pct} 100`); o.cr.classList.toggle('hide', f); o.hueco.classList.toggle('hide', !f);
    { const Ln = minaLineas(e.nombre, 20), ex = 14 * (Ln.length - 1); minaTexto(o.nom, Ln, 0, -67 - ex, 14); o.caja.setAttribute('y', -84 - ex); o.caja.setAttribute('height', 40 + ex); } o.pct.textContent = f ? '✔ en el carro' : `${e.pct}%`; o.logrado.textContent = e.pct + '%';
    o.tt.textContent = `${e.nombre}: ${e.pct}%`; o.g.classList.toggle('sel', MINA.sel === e.L);
    if (f) fins.push({e, col: o.col});
  });
  MINA.gemas.innerHTML = '';
  fins.forEach(({e, col}, k) => { const x = -46 + (k % 5) * 23, y = -60 - Math.floor(k / 5) * 18;
    const g = sv('g', {class: 'gema', tabindex: 0, role: 'button', transform: `translate(${x} ${y}) scale(1.35)`}, MINA.gemas); g.dataset.l = e.L;
    sv('path', {d: 'M0 -11 L9 -3 L5 9 L-5 9 L-9 -3 Z', fill: col, stroke: '#fff', 'stroke-width': 1.5}, g);
    sv('title', {}, g).textContent = e.nombre + ' (100 %)'; });
  MINA.carroT.textContent = fins.length ? `${fins.length} listo(s)` : 'vacío';
  // el pollito cava en el objetivo en curso, en la punta de su galería (la tarea que se está haciendo)
  // el pollito va donde de verdad se está trabajando: la galería cuyo avance cambió más recientemente
  // (las tarjetas de proceso se actualizan solas; una tarjeta de pedido puede repetir el mismo trabajo y no debe atraerlo)
  const ahora = Date.now(); MINA.cambio = MINA.cambio || {}; MINA.ult = MINA.ult || {};
  E.idiomas.forEach(e => { const k = e.pasos.map(p => p[1]).join(','); if (MINA.ult[e.L] !== undefined && MINA.ult[e.L] !== k) MINA.cambio[e.L] = ahora; MINA.ult[e.L] = k; });
  const pend = E.idiomas.map((e, i) => [e, i]).filter(([e]) => !finM(e));
  const reciente = pend.filter(([e]) => enCurso(e) && ahora - (MINA.cambio[e.L] || 0) < 15 * 60000).sort((a, b) => MINA.cambio[b[0].L] - MINA.cambio[a[0].L])[0];
  // proceso que corre en el equipo («Render de la imagen (Chrome) · es») → la tarjeta de ese idioma
  const enProc = (E.procesos || []).map(p => (String(p[0]).match(/·\s*([a-z]{2,3})\s*$/) || [])[1]).filter(Boolean);
  const porProc = pend.find(([e]) => !e.tarea && enProc.includes(e.L));
  const act = porProc || reciente || pend.find(([e]) => enCurso(e) && !e.tarea) || pend.find(([e]) => enCurso(e)) || pend.find(([e]) => e.pct > 0) || pend[0];
  let x, y, izq = false, quieto = true, fiesta = false;
  if (act) {
    const [e, i] = act, G = MINA.gal[i], c = cavado(e);
    const a = G.fondo.getPointAtLength(Math.max(0, G.L * c.f - 14)), b = G.fondo.getPointAtLength(Math.min(G.L, G.L * c.f + 4));
    x = a.x; y = a.y + 12; izq = b.x < a.x - .5; if (c.f < .02) { x = X0 + 8; y = G.y + 12; }
    quieto = !enCurso(e) && !(E.procesos && E.procesos.length);
  } else { x = 520; y = 100; fiesta = true; }
  // ¿hay algo que debe hacer el usuario? el pollito se da vuelta, lo mira de frente y se lo dice en un globo
  const acc = (E.checklist && E.checklist.acciones) || [], hay = acc.length > 0;
  MINA.pollo.classList.toggle('atiende', hay);
  minaGlobo(hay ? acc : null, x, y);
  MINA.pollo.style.transform = `translate(${x}px, ${y}px)`; MINA.giro.setAttribute('transform', izq && !hay ? 'scale(-1 1)' : '');
  MINA.pollo.classList.toggle('quieto', quieto || fiesta || hay); MINA.pollo.classList.toggle('fiesta', fiesta && !hay);
  MINA.pollo.classList.toggle('suda', cpu > 90); MINA.pollo.classList.toggle('piensa', ram > 90);
  // varias tareas a la vez (otras galerías con avance en los últimos 10 min, o procesos de otros idiomas): un pollito igual
  // trabajando en cada una; si se trabaja en una sola, no aparece ninguno extra
  MINA.extras.innerHTML = '';
  if (act) pend.filter(([e]) => e !== act[0] && enCurso(e) && (ahora - (MINA.cambio[e.L] || 0) < 10 * 60000 || (!e.tarea && enProc.includes(e.L)))).forEach(([e, i]) => {
    const G = MINA.gal[i], c = cavado(e); if (c.f < .02) return;
    const a = G.fondo.getPointAtLength(Math.max(0, G.L * c.f - 14)), b = G.fondo.getPointAtLength(Math.min(G.L, G.L * c.f + 4));
    const g = sv('g', {class: 'pollo' + (cpu > 90 ? ' suda' : ''), transform: `translate(${a.x} ${a.y + 12})`}, MINA.extras), cl = MINA.giro.cloneNode(true);
    cl.setAttribute('transform', b.x < a.x - .5 ? 'scale(-1 1)' : ''); g.appendChild(cl); });
  if (MINA.sel) minaDetalle();
  if (MINA.modal) minaModal();
  minaEncuadre();
}
function minaModal() {
  const m = MINA.modal, box = $('#minaModal'); if (!m || !MINA.E) { box.hidden = true; return; }
  if (m.accion) {   // lo que debe hacer el usuario
    const acc = (MINA.E.checklist && MINA.E.checklist.acciones) || [];
    if (!acc.length) { minaCerrar(); return; }
    $('#mCont').innerHTML = `<p class="mObj">El pollito necesita su ayuda</p><h3 id="mTit">🙋 Acción pendiente${acc.length > 1 ? 's' : ''}</h3>` +
      acc.map(a => `<div class="mAccion"><b>${esc(a[1])}</b>${a[2] ? `<p>${esc(a[2])}</p>` : ''}<small>desde las ${esc(a[0])}</small></div>`).join('') +
      `<div class="mAcc"><button type="button" id="mVolver">← Volver al mapa</button></div>`;
    if (box.hidden) { box.hidden = false; $('#mVolver').focus(); } return;
  }
  if (m.det) {   // detalle de un objetivo o del carro, en ventana (pantalla completa)
    $('#mCont').innerHTML = `<div class="mDet">${$('#minaDet').innerHTML.replace(/<h3>/, '<h3 id="mTit">')}</div><div class="mAcc"><button type="button" id="mVolver">← Volver al mapa</button></div>`;
    if (box.hidden) { box.hidden = false; $('#mVolver').focus(); } return;
  }
  const e = MINA.E.idiomas.find(x => x.L === m.L), p = e && e.pasos[m.j];
  if (!p) { MINA.modal = null; box.hidden = true; return; }
  const c = cavado(e), v = finM(e) ? 100 : p[1], est = v >= 100 ? [2, '✔ Terminada'] : (m.j === c.act ? [1, '⛏ En curso'] : (v > 0 ? [1, 'Iniciada'] : [0, 'Pendiente']));
  const procs = v < 100 && m.j === c.act && MINA.E.procesos && MINA.E.procesos.length ? MINA.E.procesos.map(x => esc(Array.isArray(x) ? `${x[0]} · ${Math.floor(x[1] / 60)} min` : String(x))).join('<br>') : '';
  $('#mCont').innerHTML = `<p class="mObj">${esc(e.nombre)} · tarea ${m.j + 1} de ${e.pasos.length}</p>
    <h3 id="mTit">${esc(p[0])}</h3><span class="mEst e${est[0]}">${est[1]}</span>
    <div class="mPct"><b>${v}%</b><div class="mBar"><i style="width:${v}%"></i></div></div>
    <dl><dt>Proceso</dt><dd>${esc(p[2] || (v >= 100 ? 'Completado' : v > 0 ? 'En proceso' : 'Todavía no empieza'))}</dd>
      ${procs ? `<dt>En el equipo</dt><dd>${procs}</dd>` : ''}
      <dt>Objetivo</dt><dd>${e.pct}% del total${finM(e) ? ' · en el carro minero' : ''}</dd></dl>
    <div class="mAcc"><button type="button" id="mVolver">← Volver al mapa</button></div>`;
  if (box.hidden) { box.hidden = false; $('#mVolver').focus(); }
}
function minaCerrar() { MINA.modal = null; $('#minaModal').hidden = true; }
document.addEventListener('click', ev => {
  if (ev.target.closest('#mVolver') || ev.target.id === 'minaModal') { minaCerrar(); return; }
  if (ev.target.closest('#minaFS, #minaFSsalir')) { minaPantalla(); return; }
  if (ev.target.closest('#minaV .globo')) { MINA.modal = {accion: true}; minaModal(); return; }
  const t = ev.target.closest('#minaV .tarea');
  if (t) { MINA.modal = {L: t.dataset.l, j: +t.dataset.j}; minaModal(); return; }
  const g = ev.target.closest('#minaV .gema, #minaV .obj'), c = ev.target.closest('#minaV .carro');
  if (g) { MINA.sel = g.dataset.l; } else if (c) { MINA.sel = '__carro'; } else return;
  if (minaEnFS()) MINA.modal = {det: MINA.sel};
  if (MINA.E) mina(MINA.E); minaDetalle(); if (MINA.modal) minaModal();
});
// pantalla completa de la mina (API Fullscreen; si no existe, p. ej. iPhone, ocupa toda la ventana con CSS)
const minaTelefono = () => minaMovil() && Math.min(screen.width, screen.height) < 600;   // teléfono (en tablet no se gira el mapa)
const minaMovil = () => matchMedia('(pointer:coarse)').matches || (navigator.maxTouchPoints > 0 && Math.min(screen.width, screen.height) < 820);
function minaPantalla() {
  const v = $('#minaMapa'), doc = document, fsEl = doc.fullscreenElement || doc.webkitFullscreenElement || doc.webkitCurrentFullScreenElement;
  if (fsEl || v.classList.contains('fsPseudo')) {
    if (fsEl) (doc.exitFullscreen || doc.webkitExitFullscreen || doc.webkitCancelFullScreen).call(doc); v.classList.remove('fsPseudo'); minaBotonFS(); return;
  }
  const req = v.requestFullscreen || v.webkitRequestFullscreen || v.webkitRequestFullScreen;
  if (minaMovil() && req) Promise.resolve(req.call(v)).then(() => screen.orientation && screen.orientation.lock && screen.orientation.lock('landscape').catch(() => {})).catch(() => v.classList.add('fsPseudo')).finally(minaBotonFS);   // móvil: toda la pantalla, en horizontal si se puede
  else { v.classList.add('fsPseudo'); minaBotonFS(); }                                                               // escritorio: todo el navegador
}
const minaEnFS = () => !!(document.fullscreenElement || document.webkitFullscreenElement || document.webkitCurrentFullScreenElement) || $('#minaMapa').classList.contains('fsPseudo');
// el mapa entra entero y el cielo / la tierra se extienden hasta los bordes: llena la pantalla sin deformarse ni cortarse
function minaEncuadre() {
  const s = $('#minaS'); if (!s || !MINA.H) return; const H = MINA.H;
  if (!minaEnFS()) { $('#minaMapa').classList.remove('girado'); s.style.height = '';
    // el mapa mide lo que ocupa su contenido (sin cielo ni tierra de más); si no cabe en la ventana se achica y se ve entero
    const c = minaCaja(), h0 = Math.min(c.w * H / 1000, c.h); s.style.height = h0 + 'px'; const a = c.w / h0;
    if (a >= 1000 / H) { const w = H * a; s.setAttribute('viewBox', `${(1000 - w) / 2} 0 ${w} ${H}`); } else { const h = 1000 / a; s.setAttribute('viewBox', `0 ${(H - h) / 2} 1000 ${h}`); }
    return; }
  s.style.height = '';
  // celular en vertical: el mapa se gira 90° para usar toda la pantalla (se intenta además bloquear la orientación horizontal)
  const m = $('#minaMapa'), gir = minaTelefono() && innerHeight > innerWidth; m.classList.toggle('girado', gir);
  const r = m.getBoundingClientRect(), a = gir ? r.height / Math.max(1, r.width) : r.width / Math.max(1, r.height);
  if (a >= 1000 / H) { const w = H * a; s.setAttribute('viewBox', `${(1000 - w) / 2} 0 ${w} ${H}`); }
  else { const h = 1000 / a; s.setAttribute('viewBox', `0 ${(H - h) / 2} 1000 ${h}`); }
}
function minaBotonFS() {
  const on = minaEnFS(), b = $('#minaFS');
  b.textContent = on ? '✕ Salir de pantalla completa' : '⛶ Pantalla completa'; b.setAttribute('aria-pressed', on);
  document.body.style.overflow = $('#minaMapa').classList.contains('fsPseudo') ? 'hidden' : '';
  requestAnimationFrame(minaEncuadre);
}
addEventListener('resize', () => { if (MINA.E && MINA.key !== minaClave(MINA.E)) mina(MINA.E); else minaEncuadre(); });
// Safari (iPad) informa el tamaño nuevo tarde al girar: se reencuadra varias veces
addEventListener('orientationchange', () => [100, 350, 700, 1200].forEach(t => setTimeout(() => { if (minaEnFS()) minaEncuadre(); }, t)));
['fullscreenchange', 'webkitfullscreenchange'].forEach(t => document.addEventListener(t, () => [100, 400].forEach(d => setTimeout(minaEncuadre, d))));
['fullscreenchange', 'webkitfullscreenchange'].forEach(t => document.addEventListener(t, minaBotonFS));
document.addEventListener('keydown', ev => { if (ev.key === 'Escape') { if (!$('#minaModal').hidden) minaCerrar(); else if ($('#minaMapa').classList.contains('fsPseudo')) { $('#minaMapa').classList.remove('fsPseudo'); minaBotonFS(); } } });
// al elegir la vista Mina, el mapa sube hasta arriba de la ventana y la ocupa entera
document.addEventListener('click', ev => { if (ev.target.closest && ev.target.closest('#vistas button[data-v=mina]')) setTimeout(() => { const m = $('#minaV'); if (m) m.scrollIntoView({block: 'start'}); }, 300); });
document.addEventListener('keydown', ev => { if ((ev.key === 'Enter' || ev.key === ' ') && ev.target.closest && ev.target.closest('#minaV [role=button]')) { ev.preventDefault(); ev.target.dispatchEvent(new MouseEvent('click', {bubbles: true})); } });
'''


def aplicar(s):
    """Inserta (o reemplaza) la vista en el texto de avance.py."""
    import re
    if 'id="minaV"' in s:   # ya estaba: quitar la versión anterior
        s = re.sub(r'\n#minaV\{.*?#minaDet li small\{[^\n]*\n', '\n', s, count=1, flags=re.S)
        s = re.sub(r'\n<section id="minaV".*?</section>', '', s, count=1, flags=re.S)
        s = re.sub(r'\n// ---- vista «Mina».*?(?=\nfunction organizar\(E\) \{)', '', s, count=1, flags=re.S)
    else:
        s = s.replace('<button data-v="tablero">Tablero</button>', '<button data-v="tablero">Tablero</button><button data-v="mina">Mina</button>', 1)
        s = s.replace("$('#tablaV').classList.toggle('hide', VISTA !== 'tabla');",
                      "$('#tablaV').classList.toggle('hide', VISTA !== 'tabla'); $('#minaV').classList.toggle('hide', VISTA !== 'mina'); if (VISTA === 'mina') mina(E);", 1)
    assert '</style></head>' in s
    s = s.replace('</style></head>', CSS + '</style></head>', 1)
    i = s.index('<section id="tablaV"'); j = s.index('</section>', i) + len('</section>')
    s = s[:j] + '\n' + HTML + s[j:]
    s = s.replace('function organizar(E) {', JS + '\nfunction organizar(E) {', 1)
    return s


if __name__ == '__main__':
    import sys
    p = sys.argv[1]; s = open(p).read(); n = aplicar(s)
    assert n.count('id="minaV"') == 1 and n.count('// ---- vista «Mina»') == 1 and n.count('data-v="mina"') == 1 and 'mina(E)' in n
    open(p, 'w').write(n); print('MINA_OK', p)
