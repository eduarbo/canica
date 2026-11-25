# Pruebas del motor en Scarab

## RC37 · El selector con la columna de la lista de juegos y en Extras

El ejecutable es nuevo (parche 0132): el selector toma la vista «switcher» del tema y enlaza sus elementos al juego mostrado, como la lista de juegos enlaza los suyos; el tema le da la misma columna que la lista, sin los gatillos que cambian de consola, con L1 y R1 bajo la captura. Una colección automática nueva, «continue», abre el selector desde Extras → Continuar. La vista de la lista de juegos del tema es idéntica a la de RC36. En la consola, con una vista previa: Extras muestra «Continuar» primero, A abre el selector y B vuelve; FN + SELECT sigue igual.

## RC36 · Selector, actividad, batería y actualizaciones para todos

El ejecutable es nuevo (parches 0129 a 0131). FN + SELECT abre el selector de juegos, que dibuja el tema; START → Canica tiene «Continuar un juego», «Actividad» y, con el actualizador del kit, la versión y las actualizaciones; una actualización se muestra como una terminal (`POST /job-console`) y pregunta «Más tarde / Actualizar ahora». El tiempo de juego cuenta sólo con la consola despierta. El kit añade `updater.py` (preguntar, automáticas o desactivadas; firma con las llaves del kit) y `guard.py` (FN + SELECT dentro de un juego; guardar y apagar con la batería agotada), que el servicio arranca antes de sus comprobaciones.

Pruebas: actualizador 23, vigía 10, instalador 14 y adaptador 7, fuera de la consola; ensayo del servicio y ensayo de una actualización completa en el entorno ARM64 de la imagen de fábrica (el actualizador de un kit instala el siguiente con su instalador real). En la consola, con una vista previa sin instalar (24 nov): FN + SELECT dentro de un juego de Game Boy cerró el juego, RetroArch escribió su partida automática con su captura, el archivo de la partida del juego no cambió y el menú abrió el selector con ese juego.

## RC35 · El progreso como aviso del tema

El panel de RC34 usaba la caja de descargas del menú, que con este tema queda sin fondo, estrecha y sobre la cabecera. El ejecutable nuevo muestra el progreso de un trabajo externo como un aviso del tema que se queda en pantalla: título, detalle y barra (`POST /progress-notice`). El lanzador, el vigilante y el servicio son los mismos; el ensayo del servicio en Linux ARM64 se repitió con este ejecutable.

## RC34 · Panel de progreso

El ejecutable es nuevo: añade al menú una entrada (`POST /progress`) con la que un trabajo externo abre, actualiza y cierra el panel de progreso del propio menú. El instalador y el generador de tarjetas dicen por dónde van, y el actualizador del kit lo muestra en un solo panel en vez de avisos repetidos. El lanzador, el vigilante y el servicio son los mismos; el ensayo del servicio en Linux ARM64 se repitió con este ejecutable.

## RC33 · Sugerencias fijas por día y versión a la vista

El ejecutable es nuevo: se compiló desde estas fuentes con el cambio 0126, que da a cada estante su propia secuencia según la fecha local. «Todos los juegos», «Sugerencias del chef» y las sugerencias de cada consola salen en el mismo orden cada vez que arranca el menú ese día, y cambian al día siguiente. El Inicio muestra la versión del kit bajo la lista de la biblioteca. El lanzador, el vigilante y el servicio son los mismos; el ensayo del servicio en Linux ARM64 se repitió con este ejecutable.

## RC32 · Logos de consola

El tema lleva los logos de consola de Art Book Next (CC BY-NC-SA 2.0) en `art/logos` y los usa cuando no hay un PNG propio en la carpeta de decoraciones. Comparada con RC31, cambian `theme.xml`, la guía, los avisos y el inventario que sella el servicio; el ejecutable, el lanzador y el vigilante son los mismos.

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
