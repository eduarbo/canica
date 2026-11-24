# Pruebas del motor en Scarab

## RC31 · Esquinas de la tarjeta enfocada

En la tarjeta enfocada, el vídeo y la captura que lo precede se recortan con el mismo radio que la imagen. En Iris, el aro de selección llega al borde de la tarjeta y cubre ese recorte. Comparada con RC30.1, cambian `theme.xml`, `art/iris/focus.png`, la guía y el inventario que sella el servicio; el ejecutable, el lanzador y el vigilante son los mismos.

## RC30.1 · Licencias

Comparada con RC30, conserva el ejecutable, el lanzador, el vigilante y todos los recursos visuales y de navegación del tema. Cambian los avisos, la guía del tema y el inventario que sella el servicio, y se añaden los textos de CC BY-SA 4.0 y MIT. Las pruebas en consola de las secciones siguientes corresponden a las candidatas que nombran.

## RC29.1 · Canica con los forks

La galería pública muestra el framebuffer físico de la RG35XX H en Iris y Ámbar. La comprobación de partidas usa Adventure Island III con el núcleo FCEUmm y copias aisladas de las ranuras de la tarjeta. El arranque desde una microSD limpia sigue pendiente. [Grabaciones y controles](https://github.com/eduarbo/canica/blob/main/docs/canica-en-accion.md)

## RC28 · Prueba histórica del tema compatible

En una RG35XX H con Scarab del 11 de mayo de 2026 se verificó la huella del EmulationStation de fábrica y la selección de Canica Ámbar. El menú mostró 617 juegos en Arcade y 313 en Arcade TATE. La cuadrícula de consolas recuperó los fondos a partir del catálogo y de las ilustraciones locales. Las tarjetas con vídeo atenúan las insignias desde que reciben el foco. El frontend ampliado añade los eventos de reproducción y la búsqueda por palabras.

Las capturas públicas de ambas rutas usan ilustraciones de muestra renderizadas a 640 × 480 en ARM64 de escritorio. También se probó el tema de formato 3 en el EmulationStation original de Aloshi, revisión `9cc42ad`. El arranque del paquete ampliado desde una microSD física limpia sigue pendiente.

## Historial de pruebas anteriores

La revisión RC27.1 aclara la compatibilidad. Comparada con RC27, conserva el ejecutable, el servicio, el tema visual y sus controles. Las pruebas de RC27 que siguen corresponden al paquete con frontend modificado.

## Compatibilidad con versiones oficiales

Se extrajo `/usr/bin/emulationstation` de la imagen oficial Scarab 20260511 de la RG35XX-H y se comparó con el binario incluido en Canica. Para cada fila se verificó que la clave está en el XML del tema, que el código C++ de Canica la consulta y que la clave está en el ejecutable de Canica y ausente del de fábrica. Es una comparación de implementación. La prueba gráfica de RC27 corresponde al frontend modificado.

| Función de Canica | Clave que lee el frontend modificado |
| --- | --- |
| X abre Partidas | `esGameListXAction` |
| Tarjetas para completar palabras | `esWordComplete` |
| Avance de las vistas previas de consolas y colecciones | `esRotateConsolePreview`, `esRotateCollectionPreview` |
| Fundido al abrir el juego | `esGameLaunchTransition` |

El Scarab oficial sí ofrece búsqueda por texto. Su implementación invoca el teclado de filtro y carece de las tarjetas de palabras de Canica. [Código del filtro de Scarab](https://github.com/knulli-cfw/batocera-emulationstation/blob/4041b56a714265de81de8165b34fbd10f313a891/es-app/src/views/gamelist/ISimpleGameListView.cpp#L457) · [Versión de EmulationStation que fija KNULLI](https://github.com/knulli-cfw/knulli-linux/blob/20260511/package/emulationstation/knulli-emulationstation/knulli-emulationstation.mk)

Las mismas claves también están ausentes del código C/C++ consultado en la rama oficial de [KNULLI](https://github.com/knulli-cfw/batocera-emulationstation/tree/f7c5ae103815761ccd34bc55b021c6e150442c96) y en el [EmulationStation original](https://github.com/Aloshi/EmulationStation/tree/9cc42adff67946175d2b7e25c6ae69cc374e98a0). La compatibilidad se declara por distribución, versión y modelo probados.

## Comprobaciones del paquete combinado

| Superficie | Comprobación |
| --- | --- |
| Consola habitual, RG35XX-H | Las candidatas RC25, RC26 y RC27 comparten el mismo ejecutable ARM64. La navegación, búsqueda por palabras, partidas, reproducción y las variantes se probaron físicamente en RC25. La nueva identidad y el nuevo servicio corresponden a la prueba de laboratorio de RC27. |
| Instalador de RC27 | En un entorno Linux ARM64 aislado con el ejecutable y las herramientas originales de la imagen Scarab 20260511, se copió el ZIP, se descubrió el servicio con KNULLI, se activó dos veces y se ejecutó el binario a través del lanzador. Tras desactivarlo se ejecutó el frontend original y se comprobó su hash. |
| Instalaciones incompatibles | Un archivo omitido, otro modelo, otra versión del firmware y dos servicios de frontend alternativos, activados por separado impidieron el montaje. Con procesos ARM64 reales y respuestas HTTP simuladas se comprobó que la activación pide un reinicio limpio cuando el menú está libre, respeta un juego activo e informa del estado correcto tras desactivar y reactivar el servicio. |
| Interfaz con una biblioteca nueva | El frontend de escritorio compilado desde las mismas fuentes renderizó Iris y Ámbar a 640 × 480. Se abrió la búsqueda y se recorrió la cuadrícula con arte de demostración y sin las decoraciones personales de la consola. |
| Conservación del perfil | En el menú del frontend se cambió de RC25 a un tema de prueba, se duplicó el perfil con el nombre de Canica y se eligió Canica. EmulationStation recuperó Ámbar y la cuadrícula. |
| Decoraciones personales | El frontend dibujó el logo de GBA desde la carpeta histórica. Al agregar la carpeta de Canica, dibujó el logo nuevo en la misma posición. |
| Fuentes | Desde el ZIP de fuentes de Canica se reprodujeron byte por byte el tema, el instalable y el ZIP de fuentes usando el binario cualificado. El frontend ARM64 se recompiló desde estas fuentes en la cualificación de RC26. El instalable RC27 conserva el ejecutable cualificado. El verificador del tema recorrió las 32 combinaciones de ajustes. |

La instalación desde cero en una **microSD física independiente**, el orden de arranque de los servicios después de un apagado y la vuelta al menú original por ese mismo camino quedan pendientes. La prueba del instalador usó el arranque del lanzador con `--help` en el entorno aislado. La prueba gráfica usó Mesa y un framebuffer virtual. Los archivos se distribuyen como candidata.

El servicio se limita a la compilación de firmware cuyo frontend original tiene SHA-256 `d02c1f349952151ba5cd5b67125e848e95279483230d1582203efd44cf37af64`. El material propio usa CC BY-SA 4.0 y MIT; ver `AVISOS.md`.
