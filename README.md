# Proyecto RIT: Arañador web

**Tema:** Intervención de Estados Unidos en América Latina  

**Autores:** Elías Ramírez Hernández, Ignacio Ramírez Sandí.  

**Curso:** Recuperación de la Información Textual.  


---

## Descripción

El Desclasificador es un crawler implementado en Python que descarga y almacena, en
texto plano, documentos relacionados con la intervención de Estados Unidos en
América Latina. Consta de:

- `main.py`: orquestación del arañado, con hilo productor, trabajadores (arañas)
  concurrentes, registro de la frontera, estadísticas y apagado elegante.
- `linkHelpers.py`: descarga y procesamiento, con Selenium headless adaptativo,
  extracción de texto, detección de enlaces, políticas de cortesía, robots.txt y
  persistencia en SQLite.
- `crawler.db`: base SQLite donde viven la frontera (URLs pendientes) y los
  metadatos de cada página visitada.
- `assets/`: URLs semilla (`URLs0.txt`), dominios que se renderizan siempre con
  JavaScript (`JS0.txt`) y dominios bloqueados (`Bloqueados0.txt`).
- `HTMLs/`: repositorio de texto plano (un `.txt` por página, nombrado por su URL
  con los caracteres especiales convertidos en `_`).
- `bitacora.log`: log rotativo del recorrido (qué URL se descargó, en qué hilo, qué
  host se descartó y por qué).

### Estrategia de arañado

La frontera vive en `crawler.db`. Al iniciar se cargan las semillas
(`assets/URLs0.txt`). Un hilo productor reclama lotes de URLs pendientes, un
conjunto de hilos araña las descarga y procesa, y un hilo registrador vuelve a
meter en la base los enlaces descubiertos en cada página. La frontera crece así de
forma continua, en una exploración por amplitud aproximada con selección aleatoria,
y sobrevive a re-corridas.

---

## Necesidad de información

### Tema y características

El buscador se centra en la **intervención de Estados Unidos en América Latina**
desde mediados del siglo XX hasta hoy: golpes de Estado, operaciones encubiertas,
guerras civiles financiadas desde el exterior, presiones económicas y diplomáticas,
embargos y programas de cooperación militar.

La información requerida es **documental, textual e histórica**:

- Documentos históricos y archivos desclasificados.
- Noticias y reportajes de prensa.
- Análisis académicos y artículos de investigación.
- Declaraciones oficiales (gobiernos de EE. UU. y países latinoamericanos).
- Testimonios y crónicas de las épocas afectadas.

Se prioriza el **texto claramente redactado** (no imágenes, audio o video), lo que
coincide con el diseño del repositorio: archivos `.txt` limpios derivados del HTML
renderizado.

### Colectivo destino

Estudiantes universitarios y de posgrado, investigadores, historiadores y
periodistas de América Latina interesados en historia política comparada. El rango
etario típico es de 18 a 45 años; el contexto socioeconómico es heterogéneo, por lo
que las fuentes priorizadas son de **acceso libre y gratuito** (prensa abierta,
archivos públicos, Wikipedia).

### Subtemas de interés y consultas esperadas

- Doctrina Monroe y política del "Gran Garrote".
- Operación Cóndor y dictaduras del Cono Sur.
- Revoluciones y conflictos centroamericanos (Nicaragua, El Salvador, Guatemala).
- Cuba: embargo, Bahía de Cochinos, crisis de los misiles.
- Presiones económicas (embargos, deuda, FMI) y programas como la Alianza para el
  Progreso.

Consultas típicas: *"Operación Cóndor", "~~intervención~~ de EE. UU. en Chile",
"Golpe de Estado Guatemala 1954", "embargo Cuba", "guerra contra las drogas
Latinoamérica"*.

---

## Políticas de arañado

| Política | Descripción | Justificación |
| :--- | :--- | :--- |
| Frontera persistente en SQLite | Todas las URLs viven en `crawler.db` (tabla `paginas`, columna `url UNIQUE`). Las semillas se insertan con `INSERT OR IGNORE` al iniciar. | El estado del arañado sobrevive a caídas y re-corridas, la deduplicación es nativa y la frontera se puede consultar. |
| Reserva atómica de lotes | `reclamarLoteBD` marca las URLs reclamadas con `reservada = 1` en una sola transacción (`UPDATE ... RETURNING`). Al reiniciar, las filas reservadas que no se scrapearon vuelven a `reservada = 0`. | Evita que dos hilos descarguen la misma URL y permite recuperar el arañado tras una caída sin perder ni duplicar trabajo. |
| Cortesía por host | Separación mínima de `PAUSA_MS` (250 ms por defecto, `--pausa-host`) entre peticiones al mismo host, reservada atómicamente bajo un candado (`esperarCrawlDelay`). | No satura a los servidores de prensa y archivos abiertos que consume el colectivo destino. |
| robots.txt | Se consulta y respeta el `robots.txt` de cada host, con caché por dominio y decisión *fail-open* si el archivo es ilegible. Las variantes de edición de wiki (`?action=edit&section=...`) se colapsan a su URL base para que la decisión aplique a todas. | Uso ético de los sitios; evita que nos bloqueen. El `robots.txt` se descarga con `requests` porque el agente genérico de `urllib` recibe 403. |
| Dominios bloqueados | `assets/Bloqueados0.txt` contiene redes sociales, buscadores, publicidad, comercio y dominios problemáticos; los subdominios también quedan excluidos. | Esas páginas no aportan a la necesidad de información y desperdician presupuesto y cortesía. |
| Descarga concurrente con hilos | `--workers` (128 por defecto) hilos araña persistentes consumen una cola (`queue.Queue`). | Cumple el requisito de "descarga concurrente"; la red es I/O-bound, así que los hilos no compiten por el GIL. |
| Identificación del agente | User-Agent `El-Desclasificador/1.0` en cada petición HTTP. | Transparencia: el arañado se identifica ante los sitios. |
| Normalización de URLs | Se elimina el fragmento (`#...`) y los parámetros de rastreo (`utm_`, `fbclid`, `gclid`, `mc_`, `ref_`, `via_`, `hs_`, `spm_`) antes de registrar la URL. | Reduce duplicados aparentes que inflarían la frontera y ensuciarían la deduplicación. |
| Filtro de ámbito | Solo se aceptan URLs `http(s)` válidas; se descartan login, registro, búsquedas y binarios o multimedia (`EXCLUSIONES_URL`). Los enlaces relativos se resuelven contra la página con `urljoin`. | Evita páginas irrelevantes y descargas no textuales; amplía la frontera de forma segura. |
| Renderizado adaptativo con Selenium | Por defecto se descarga el HTML estático. Se renderiza con Chrome headless solo cuando el dominio está en `JS0.txt` (forzado), la página parece un desafío anti-bot, o el HTML estático es insuficiente (shell de React/Next/Vue, texto demasiado corto). Máximo 2 renders simultáneos y un presupuesto de 12 pruebas; los hosts que demuestran necesitar JS se marcan y se renderizan siempre. | Prensa y archivos digitales cargan contenido por JavaScript; renderizar todo sería lento, por eso se hace solo cuando se detecta que hace falta. |
| Solo texto plano | Se eliminan `<script>`, `<style>` y `<noscript>` antes de `get_text()`; `cortarTexto` normaliza (quita acentos y puntuación, minúsculas, tokens separados por espacio). | El repositorio debe ser texto procesado, no HTML ni scripts, tal como exige la rúbrica. |
| Filtro de relevancia | `puntajeRelevancia` aplica primero un filtro rápido de pistas (`PISTAS_RAPIDAS`) y luego cuenta los términos del tema presentes; solo se guarda texto con relevancia 4 o más (`MIN_RELEVANCIA`). | El repositorio se mantiene enfocado en el tema y se descarta el ruido. |
| Hosts fríos (circuit breaker) | Tras `--fallos-frio` errores seguidos de un host (403, 429 o 5xx) ese host se descarta y no se vuelve a intentar. | Evita que hilos queden atascados con servidores que nos bloquean o fallan. |
| Deduplicación | La columna `url UNIQUE` de la base hace que `INSERT OR IGNORE` deje fuera duplicados; `registrarURLsBD` devuelve cuántas URLs eran nuevas. | Evita trabajo repetido y controla el crecimiento del repositorio y de la frontera. |
| Selección aleatoria de la frontera | `reclamarLoteBD` usa `ORDER BY RANDOM()` y el productor revuelve el lote en memoria antes de encolarlo. | Reparte cada lote entre miles de hosts: la pausa por host deja de ser el cuello de botella y la descarga aprovecha la concurrencia. |
| Profundidad acotada por presupuesto | `--iters` lotes de `--lote` URLs (por defecto 40 lotes de 1000, 40 000 URLs); `--iters 0` es ilimitado. | Controla el tiempo y el volumen del repositorio. |
| Escritura por lotes | Un hilo escritor acumula 1000 resultados y actualiza la base de una vez (`UPDATE` con `titulo`, `codigo_estado`, `scrapeada = 1`, `fecha_visita`). | Reduce los bloqueos sobre SQLite y mejora el rendimiento general. |
| Mantenimiento del WAL | Un hilo de mantenimiento hace checkpoint si el WAL supera 8 MB; al cerrar el arañado se fuerza un punto de control (`wal_checkpoint(TRUNCATE)`). | Evita que el WAL crezca sin límite y acelera el apagado y la recuperación. |
| Estadísticas y auto-apagado | Cada 10 s se registran MB/s y URLs/min. Si el rendimiento baja de `--min-velocidad` (50 URLs/min) durante `--min-ventanas` ventanas (6) consecutivas, el arañado se detiene. | Evita quedarse arañando un host lento sin progreso; a la vez deja la bitácora del recorrido. |

---

## Almacenamiento y recuperación

El repositorio de datos es SQLite (`crawler.db`), un archivo único, consultable y
transaccional, suficiente para decenas de miles de páginas.

### Esquema

Tabla `paginas`:

| Columna | Significado |
| :--- | :--- |
| `id` | Clave primaria. |
| `url` | URL normalizada, `UNIQUE`. |
| `titulo` | Título de la página (o `NULL`). |
| `codigo_estado` | Código HTTP de la descarga. |
| `scrapeada` | `1` si la página ya fue procesada, `0` si está pendiente. |
| `fecha_visita` | Fecha/hora de la visita (UTC). |
| `reservada` | `1` si la URL fue reclamada por un lote en curso. |

Índice `idx_paginas_pendientes (scrapeada, id)` para consultar la frontera con
rapidez. La base se abre en modo WAL (`journal_mode = WAL`) con
`busy_timeout = 30 s` y auto-checkpoint cada 1000 páginas, lo que permite lectores
y el hilo escritor sin bloquearse.

### Ciclo de vida de una URL

Una URL aparece cuando el hilo registrador vacía la frontera en memoria cada 2 s y
la inserta con `INSERT OR IGNORE`; las repetidas se descartan por el `UNIQUE`. El
productor la reclama con `reclamarLoteBD`, que marca hasta N URLs pendientes con
`reservada = 1` en una sola transacción y las devuelve. Un hilo araña la descarga,
la puntúa y guarda el texto en `HTMLs/`. Por último, el hilo escritor la marca con
`scrapeada = 1`, `reservada = 0`, `codigo_estado`, `titulo` y `fecha_visita`.

### Recuperación ante caídas

Si el proceso se interrumpe (apagón, `kill`), quedan filas con `reservada = 1` pero
`scrapeada = 0`. Al volver a iniciar, `inicializarBD` las libera a `reservada = 0`
en bloques de 10 000. Cada URL se procesa una sola vez: las ya scrapeadas quedaron
`scrapeada = 1` y las demás vuelven a la frontera. El cierre ordenado (Ctrl+C)
fuerza además un checkpoint del WAL para dejar la base limpia.

---

## Sistema de relevancia

Cada página descargada se puntúa antes de guardarse. `TERMINOS_RELEVANTES` es
una lista de expresiones del tema, por ejemplo golpes de Estado, operaciones
encubiertas, embargos y nombres de países. `puntajeRelevancia` cuenta cuántas de
esas expresiones aparecen en el texto visible de la página.

Antes de esa cuenta hay un filtro rápido. Se comprueba si el texto en minúsculas
contiene alguna pista de una lista más corta (`PISTAS_RAPIDAS`). Si no contiene
ninguna, la página se descarta sin ejecutar la cuenta completa. Ese paso evita
gastar CPU en páginas que casi con seguridad no son del tema.

Solo se escribe en `HTMLs/` el texto con relevancia 4 o más (`MIN_RELEVANCIA`).
Las demás páginas se marcan como visitadas en `crawler.db` pero no se guardan.
El umbral se ajusta en `linkHelpers.py`.

En el arañador de Nutch la relevancia se aplica después de la descarga, en
`nutch/extract.py`, con la misma cuenta y el mismo umbral. Así el repositorio
queda igual sin importar la implementación.

---

## Selección aleatoria de la frontera

Las URLs pendientes viven en `crawler.db`. Cuando el productor reclama un lote,
la base de datos las elige al azar con `ORDER BY RANDOM()`.

La frontera puede crecer a cientos de miles de URLs repartidas en miles de
hosts. Elegir por orden de inserción concentraría cada lote en un puñado de
sitios, casi siempre los mismos. Como la cortesía por host limita las peticiones
a un mismo sitio, toda la cola terminaría esperando detrás de ese host y la
descarga se haría más lenta.

Al elegir al azar, cada lote toca muchos hosts distintos. La pausa por host se
mantiene igual de respetuosa, pero deja de ser el cuello de botella, y la
descarga aprovecha mejor la concurrencia. La elección al azar se aplica en
`reclamarLoteBD`, en `linkHelpers.py`.

---

## Metadatos almacenados

| Metadato | Dónde | Para qué política |
| :--- | :--- | :--- |
| URL, `scrapeada`, `reservada` | `crawler.db` (`paginas`) | Frontera, deduplicación, reserva y recuperación. |
| `codigo_estado`, `titulo`, `fecha_visita` | `crawler.db` (`paginas`) | Cortesía, hosts fríos y trazabilidad del recorrido. |
| Texto procesado | `HTMLs/<url>.txt` | Repositorio de documentos (solo los relevantes). |
| Recorrido de la araña | `bitacora.log` (rotativo, 50 MB) | Bitácora exigida por la rúbrica: por dónde anduvo la araña y por qué se descartó cada URL. |

---

## URLs semilla

La primera iteración parte de `assets/URLs0.txt` (28 URLs, validadas con HTTP 200):

**Panorama general del tema**
1. https://es.wikipedia.org/wiki/Intervenciones_de_Estados_Unidos_en_Am%C3%A9rica_Latina
2. https://elordenmundial.com/mapas-y-graficos/intervencionismo-estados-unidos-america-latina/
3. https://www.wola.org/
4. https://revista.drclas.harvard.edu/united-states-interventions/
5. https://www.scmp.com/news/world/united-states-canada/article/3338634/us-interventions-latin-america-history-coups-and-conflicts
6. https://mapasmilhaud.com/mapas-historicos/el-intervencionismo-de-estados-unidos-en-latinoamerica-1950-2010/
7. https://portalacademico.cch.unam.mx/historiauniversal2/america-latina-1918-1945/intervencionismo-de-eu
8. https://www.aa.com.tr/en/americas/factbox-a-history-of-us-interventions-across-the-americas/3790233

**Noticias y hechos recientes**
9. https://www.npr.org/2026/01/02/nx-s1-5652133/us-venezuela-interventionism-caribbean-latin-america-history-trump
10. https://www.vaticannews.va/es/mundo/news/2026-01/america-latina-intervenciones-militares-estadounidenses.html

**Hitos y episodios históricos**
11. https://history.state.gov/milestones/1961-1968/bay-of-pigs
12. https://es.wikipedia.org/wiki/Operaci%C3%B3n_C%C3%B3ndor
13. https://es.wikipedia.org/wiki/Intervenci%C3%B3n_estadounidense_en_golpes_de_Estado_en_Am%C3%A9rica_Latina
14. https://en.wikipedia.org/wiki/United_States_involvement_in_regime_change_in_Latin_America
15. https://es.wikipedia.org/wiki/Doctrina_Monroe
16. https://es.wikipedia.org/wiki/Crisis_de_los_misiles_de_Cuba
17. https://es.wikipedia.org/wiki/Revoluci%C3%B3n_Nicarag%C3%BCense
18. https://es.wikipedia.org/wiki/Alianza_para_el_Progreso
19. https://es.wikipedia.org/wiki/Guerra_Fr%C3%ADa

**Archivos, investigación y bibliografía**
20. https://nsarchive.gwu.edu/  (National Security Archive, documentos desclasificados)
21. https://digitalarchive.wilsoncenter.org/  (Wilson Center Digital Archive)
22. https://www.archives.gov/research/foreign-policy  (Archivo Nacional de EE. UU.)
23. https://www.cia.gov/readingroom/  (CREST, Archivo de la CIA)
24. https://www.cfr.org/latin-america  (Consejo de Relaciones Exteriores)
25. https://internationalpolicy.org/  (Center for International Policy)
26. https://www.hrw.org/es  (Human Rights Watch)
27. https://www.telesurtv.net/  (prensa regional)
28. https://dialnet.unirioja.es/buscar/documentos?querysDisponibles=BIBLIOGRAFICA_BUSQUEDA_GENERAL&texto=intervencionismo+estados+unidos+america+latina  (búsqueda bibliográfica en Dialnet)

> La selección prioriza fuentes abiertas, estables y accesibles para el colectivo
> (imparten el tema), y entremezcla puntos de entrada (Wikipedia, prensa, archivos,
> buscadores académicos) para diversificar la frontera de la primera iteración.

---

## Instalación y uso

```bash
pip install -r requirements.txt
# (Selenium Manager descargará automáticamente el driver de Chrome)
python3 main.py
```

Opciones principales:

| Argumento | Por defecto | Descripción |
| :--- | :--- | :--- |
| `--workers` | 128 | Número de hilos araña. |
| `--lote` | 1000 | URLs por lote encolado. |
| `--iters` | 40 | Lotes totales (presupuesto); `0` = ilimitado. |
| `--no-robots` | No | Ignorar `robots.txt`. |
| `--pausa-host` | 250 | Separación mínima en ms entre peticiones al mismo host. |
| `--fallos-frio` | 3 | Errores seguidos para descartar un host. |
| `--min-velocidad` | 50 | URLs/min bajo las cuales detenerse. |
| `--min-ventanas` | 6 | Ventanas de 10 s de rendimiento bajo antes de detenerse. |
| `--js` | No | Renderizar con Selenium (lento); por defecto es estático. |

El arañado corre de forma autónoma y se reanuda desde donde quedó si se vuelve a
ejecutar. La bitácora (`bitacora.log`) documenta el recorrido y las decisiones de
descarte.