# Comparación de las implementaciones del arañador

Dos arañadores para la misma necesidad de información (intervención de EE. UU.
en América Latina): el propio en Python y uno sobre Apache Nutch.

## Resumen

| | Python (propio) | Apache Nutch |
| :--- | :--- | :--- |
| **Tipo** | Arañador propio, frontera continua | Marco de arañado completo |
| **Frontera / cola** | Implementada (productor + cola) | CrawlDb |
| **robots.txt** | `robotparser` | Integrado |
| **Cortesía por host** | pausa de 250 ms | `fetcher.server.delay` |
| **Concurrencia** | hilos (`--workers`) | `fetcher.threads.fetch` |
| **Parseo** | BeautifulSoup (lxml) | parse-html / parse-tika |
| **Repo de texto** | `HTMLs/` (cortarTexto) | segmentos -> `HTMLs/` |
| **Metadatos** | SQLite (`crawler.db`) | CrawlDb + segmentos |
| **Bitácora** | `bitacora.log` | `logs/bitacora_nutch.log` |
| **Rendimiento observado** | ~500 URLs/min | pocas URLs por segmento pequeño; escala con hilos y hosts |

## Ventajas y desventajas

### Apache Nutch

- **Ventajas**: maduro y probado en producción; robots.txt y cortesía por host
  integrados; escala a clústeres Hadoop; el plugin parse-tika reconoce muchos
  formatos; el CrawlDb guarda el estado de cada URL.
- **Desventajas**: sobrecarga por ciclo (inject/generate/fetch/parse/updatedb
  levantan jobs de Hadoop local); infraestructura pesada (JDK 17, distribución
  grande, logs de Hadoop); menos control fino sobre el procesamiento por página,
  porque la relevancia se aplica después, en `extract.py`; más lento en modo
  local para decenas de miles de URLs.

### Python (propio)

- **Ventajas**: simple, didáctico y todo visible; mismo formato de salida que
  Nutch; rápido para el objetivo (~500 URLs/min, estático por defecto).
- **Desventajas**: el GIL limita el trabajo de CPU (parseo); sesiones por hilo;
  menos robusto que Nutch ante sitios difíciles.

## Viabilidad (rubro "en qué casos es o no viable")

- **Nutch es viable** cuando el volumen es de millones de URLs, se requiere
  distribución o clúster, o se prefiere un marco mantenido por la comunidad con
  robots y cortesía ya resueltos. No es viable para un arañado enfocado y
  acotado con fecha límite: la sobrecarga por ciclo y la configuración pesada no
  se justifican para miles de URLs, y la relevancia debe post-procesarse.
- **El arañador propio es viable** para este repositorio (10 GB, decenas de
  miles de páginas): rápido, controlado y ligero. No es viable para la escala de
  un buscador, donde Nutch o Scrapy brillan.

Conclusión: las dos implementaciones resuelven la misma necesidad. Nutch aporta
robustez y escala a costa de peso y control; el propio aporta velocidad y
control fino a costa de implementar la infraestructura.