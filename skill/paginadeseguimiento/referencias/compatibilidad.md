# Compatibilidad de la página de seguimiento

El usuario la mira también en un **iPad mini 2 (iOS 12, Safari 12)**. Todo cambio debe funcionar ahí.

- CSS que Safari 12 no conoce: `inset` (usar `top/right/bottom/left:0`), `:is()`, `dvh` sin respaldo (poner antes `100vh`), `gap` en flex (solo estética), `aspect-ratio`.
- JS que rompe el script entero en Safari 12: `?.`, `??`, `||=`, `replaceAll`, `matchAll`, `.at()`, lookbehind `(?<=`, `structuredClone`. Antes de publicar, buscar estos patrones en `avance.py`.
- Un `<iframe>` no se desplaza en iOS: la portada fija abre el túnel directamente en iPad/iPhone; el «Sin Conexión» vive también dentro de la página (`sin_conexion.py`) y salta solo al túnel nuevo leyendo `tunel.json` de GitHub.
- Animaciones que deben andar en Safari 12: SMIL (`<animateTransform>`) para el brazo del pollito (giro desde el hombro); CSS para el resto.
- Pantalla completa: escritorio = toda la ventana del navegador (clase `fsPseudo`); móvil = Fullscreen API (`webkitRequestFullscreen` en iPad). El mapa solo se gira 90° en teléfonos (lado menor < 600 px); al girar el equipo se reencuadra varias veces (100–1200 ms), porque Safari informa el tamaño nuevo tarde.
- Cuidado al aplicar `mina_vista.py`: inserta su CSS antes de `</style></head>`; `sin_conexion.py` inserta HTML entre `<body>` y `<main>`. No volver a anclar en `</style></head><body><main>`.
- Probar con la emulación de Chrome DevTools: `768x1024x2,mobile,touch` y `1024x768x2,mobile,touch,landscape` con el userAgent de iPad iOS 12; y `390x844x3,mobile,touch` para teléfono.
- **Nunca mezclar `:fullscreen` con otros selectores en la misma regla**: Safari 12 no lo conoce y descarta la regla entera (también `.fsPseudo`). Una regla por selector, más la variante `:-webkit-full-screen`. API vieja: `webkitRequestFullScreen`, `webkitCurrentFullScreenElement`, `webkitCancelFullScreen`.
