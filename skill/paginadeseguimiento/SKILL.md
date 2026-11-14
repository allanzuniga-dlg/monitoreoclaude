---
name: paginadeseguimiento
description: Página de seguimiento EN VIVO para cualquier proyecto o tarea de varios pasos (videos, reportes, desarrollos, migraciones…), con enlace fijo en GitHub Pages, vistas Tarjetas / Tabla / Tablero / Mina (pollito minero que cava hacia cada objetivo), monitor de CPU y RAM, acciones pendientes para el usuario y pollito durmiendo «Sin Conexión». Úsala siempre que el usuario pida "página de seguimiento", "página de avance", "quiero ver el avance", "seguimiento en vivo", "el pollito minero", "monitoreo del proceso", o al empezar cualquier trabajo largo de varios pasos que el usuario quiera seguir desde fuera de la computadora.
---

# Página de seguimiento

Página web en vivo del avance de un trabajo, servida desde esta computadora (`avance.py`, puerto 8765) y publicada en internet con un túnel de Cloudflare. El usuario entra siempre por el **enlace fijo**:

**https://allanzuniga-dlg.github.io/monitoreoclaude/**

La portada fija (repo público `allanzuniga-dlg/monitoreoclaude`, GitHub Pages) muestra la página del túnel en vivo; si no responde, un pollito durmiendo con «Sin Conexión». En iPad / iPhone abre la página del túnel directamente (en Safari un marco no se desplaza).

## Empezar

```bash
~/.claude/skills/paginadeseguimiento/iniciar.sh "<carpeta del proyecto>" "Qué se está haciendo"
```

Crea `<carpeta>/seguimiento/` con la plantilla, pone el título, levanta la página y el túnel, y publica la dirección del túnel en el enlace fijo. **Dar siempre el enlace fijo en el chat** (no el de trycloudflare). Una sola página en vivo a la vez: el enlace fijo muestra el último proyecto publicado.

Proyecto de videos ABC Dust: la skill `videos_abcdust` trae su propia copia en la plantilla (tarjetas por idioma calculadas solas); se usa igual.

## Contar el avance (desde `<carpeta>/seguimiento/`)

| Qué | Comando |
|---|---|
| Título (solo qué se trabaja) | `python3 -I paso.py --trabajo "Informe mensual de soporte"` |
| Tarjeta = objetivo, con sus tareas en orden | `python3 -I paso.py --tarea <id> "Nombre del objetivo" "Tarea 1\|Tarea 2\|Tarea 3"` |
| Avance de una tarea (0–100) y detalle | `python3 -I paso.py --tarea-paso <id> <n.º desde 1> <pct> "3 de 8 gráficos"` |
| Línea del registro de actividad | `python3 -I paso.py "Lo que acabo de hacer"` |
| Algo que debe hacer el usuario (frena el trabajo) | `python3 -I paso.py --accion "Qué hacer" "Cómo hacerlo"` |
| Acción resuelta | `python3 -I paso.py --accion-hecha "<inicio del texto>"` |
| Reiniciar solo la página (mismo enlace) | `./publicar_avance.sh --pagina` |
| Detener todo | `./publicar_avance.sh --parar` |

Reglas:
- **Cada instrucción nueva del usuario va enseguida a una tarjeta** (o a un paso de una tarjeta existente).
- Las tareas de una tarjeta van **en el orden en que se hacen**: la excavación de la Mina es secuencial (las anteriores completas + el % de la actual).
- **No repetir el mismo trabajo en dos tarjetas** (confunde: dos porcentajes suben a la vez y parece que se hacen dos cosas).
- Actualizar el % de la tarea en curso a medida que avanza: el pollito va a la galería que cambió más recientemente (o a la del proceso que corre en el equipo, si `avance.py` lo reconoce).
- **Cada archivo subido a Drive se registra con `paso.py --drive <id de la tarjeta o idioma> <url>`**: el botón «▶ Ver en Drive» aparece **en esa sección** (su tarjeta en Tarjetas/Tabla/Tablero y un ▶ azul a la izquierda del círculo de su objetivo en la Mina), no como botón general. Dar también el enlace en el chat. Los enlaces de las acciones pendientes se abren y se copian.
- **Lo terminado lo limpia el usuario**: cada objetivo al 100 % muestra en la Mina una **escobilla** a la derecha del círculo del 100 %; al tocarla (confirmación en una ventana pequeña al centro con el diseño de la página, nunca `confirm`/`alert` del navegador: en el celular se ven mal) la página llama `POST /limpiar` y la tarjeta se quita (las de idioma se ocultan con `ocultas` en `checklist.json`) y el mapa se reacomoda. No quitar tarjetas terminadas por cuenta propia salvo que el usuario lo pida.
- `--accion` solo para lo que frena el trabajo y depende del usuario (iniciar sesión, aprobar, elegir). Aparece en naranja arriba y en la Mina el pollito se da vuelta y lo dice en un globo.

## Vistas (botones arriba; se recuerda por navegador)

- **Tarjetas / Tabla / Tablero**: avance por objetivo, con sus tareas y el registro de actividad.
- **Mina** (`mina_vista.py`): cada tarjeta es un objetivo (cristales al final de su galería); cada tarea es un tramo de la galería. Cada tramo sin cavar es **tierra con piedras**; el pollito, dentro del túnel, pica la orilla justo en el % de la tarea (el túnel oscuro es lo ya cavado, y todo tramo al 100 % se ve despejado aunque esté más adelante). Una tarea sin terminar muestra su nombre y % centrados en su tramo; al 100 % aparece su tarjeta (así la pantalla no se recarga ni se solapan los rótulos). Los nombres nunca se cortan: van en varias líneas. Fuera de pantalla completa el mapa mide lo que ocupa su contenido (sin cielo ni tierra de más; se achica si no cabe) y al elegir «Mina» la página sube hasta él. **Si se trabaja en varias tareas a la vez** (otras galerías con avance en los últimos 10 min o procesos de otros idiomas), aparece otro pollito igual cavando en cada una; con una sola tarea, uno solo. El pollito minero (casco con linterna, pico sostenido con el ala) cava donde se está trabajando. Al 100 % el objetivo va al carro minero. Tocar una tarea abre una ventana con el proceso, el % y «Volver al mapa»; tocar un objetivo, una gema o el carro muestra el detalle de lo finalizado. CPU > 90 %: el pollito suda; RAM > 90 %: nube con un cerebro que palpita; barras animadas de CPU y RAM y etiqueta de avance total en el mapa. Pantalla completa: solo el mapa, de borde a borde (escritorio: la ventana del navegador; celular: la pantalla, girada en teléfonos en vertical), con un ícono discreto arriba a la derecha para salir.
- **Monitor del sistema** a la derecha (CPU por núcleo, RAM, swap, procesos que más consumen).

## Archivos de la plantilla

| Archivo | Para qué |
|---|---|
| `avance.py` | Servidor de la página (rutas `/`, `/ws`, `/eventos`, `/estado`; nada más del proyecto). Ya trae la Mina y «Sin Conexión» aplicadas |
| `paso.py` | Escribe `checklist.json` (tarjetas, acciones, registro) |
| `publicar_avance.sh` | Página + túnel; publica el túnel en el enlace fijo |
| `mina_vista.py`, `sin_conexion.py` | Fuentes de la Mina y del «Sin Conexión»; para cambiarlas: editar y `python3 mina_vista.py avance.py` (reemplaza la versión anterior) |
| `monitoreo/index.html` | Portada fija (la que vive en GitHub Pages) |
| `monitoreo/publicar_tunel.sh` | Actualiza solo `tunel.json` del repo por la API |
| `config.json` | `titulo`, `solo_tareas: true` (proyecto sin idiomas de video) |

## Seguridad

- El token de GitHub se **lee** de `~/Escritorio/Credenciales/Tokengit.txt` cada vez (o `GITHUB_TOKEN_FILE`); **nunca** se escribe en el repo, en la configuración de git ni en los logs. Antes de cada commit al repo: `grep -rIlE "ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}"` debe dar vacío.
- El repo `monitoreoclaude` es público: no poner datos del cliente, correos, tokens ni rutas privadas en la página ni en `tunel.json`.

## Compatibilidad

Ver `referencias/compatibilidad.md` (Safari 12 del iPad mini 2 del usuario: sin `inset`, sin `?.`/`??`, iframes que no se desplazan, reencuadre al girar).
