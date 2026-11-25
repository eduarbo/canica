# Reconstruir Canica

El directorio `knulli/39-canica` contiene el generador del tema. Los directorios vecinos sólo contienen los recursos que consume. La carpeta `nativo/fuente` contiene el código de EmulationStation que utiliza la candidata RC37, con los parches específicos ya aplicados. El binario incluido se identifica por SHA-256 `19f3dfe9de2b562f67590e0bd84310eeeb7b11ba02dd3f70a39231b307b036df`.

## Origen del frontend

El motor de la candidata está en la rama `main` del fork de EmulationStation. Sobre la serie de Scarab para RG35XX H, la revisión `4215ca1` añade las tarjetas de partidas y permite usar capturas con el tratamiento visual de cada sistema, `f9c8c58` hace que cada estante sugiera los mismos juegos durante todo el día `4f18ea3` muestra el progreso de una actualización como un aviso del tema que se queda en pantalla, `38c9991` dibuja una actualización como una terminal y añade START → Canica, `bf810a3` añade el selector de juegos (FN + SELECT) y la actividad, y cuenta el tiempo de juego sólo con la consola despierta, `a4687b6` deja que el tema dibuje el selector y hace de la actividad una página del menú, y `09b1db2` dibuja el selector con la columna de la lista de juegos y lo abre desde Extras. La compilación del kit aplica además los cuatro parches de empaquetado de KNULLI. La carpeta `nativo/herramientas` conserva los últimos veintidós diffs y `nativo/fuente` contiene el resultado aplicado. [Fork del frontend](https://github.com/eduarbo/batocera-emulationstation) · [Revisiones y compilación](https://github.com/eduarbo/canica/blob/main/tools/canica/README.md)

Existe también un fork del firmware para cambios de sistema como suspensión y ahorro de energía. El instalable de Canica usa la imagen oficial de Scarab y añade el frontend mediante un servicio reversible. El tercer repositorio compila y distribuye paquetes de correcciones de la consola. [Fork de KNULLI](https://github.com/eduarbo/knulli-linux) · [Paquetes de la consola](https://github.com/eduarbo/knulli-console-bundles)

## Tema

Con Python 3.9 o posterior, ImageMagick 7 y librsvg instalados, ejecuta desde la raíz de las fuentes:

```sh
python3 -B knulli/39-canica/build.py salida
python3 -B knulli/39-canica/validate.py salida/canica-1.0.1-rc37.zip
```

## Frontend

Se necesitan Docker con ejecución Linux ARM64, Git y la imagen oficial `knulli-h700-rg35xx-h-scarab-20260511.img.gz`. El script usa Debian Bookworm y las bibliotecas de esa imagen. La imagen de firmware se obtiene por separado. Antes de compilar, comprueba que su SHA-256 es `c28a96f88b07e3adb4ea76b9874cd18ae177ec216bec2dac87c68795fb81291c`. [Versiones de KNULLI](https://github.com/knulli-cfw/distribution/releases)

Desde la raíz de las fuentes, con una copia de trabajo temporal:

```sh
tmp_src=$(mktemp -d)
cp -R nativo/fuente/. "$tmp_src/"
git -C "$tmp_src" init -q
git -C "$tmp_src" add locale
DOCKER_DEFAULT_PLATFORM=linux/arm64 bash nativo/herramientas/build-es.sh /ruta/knulli-h700-rg35xx-h-scarab-20260511.img.gz "$tmp_src" "$PWD/salida/bin"
```

El binario incorpora la hora de compilación. La comparación del ZIP del tema se puede hacer byte a byte con las mismas versiones de las herramientas. Las pruebas del frontend y del servicio se documentan en `PRUEBAS.md`.

## Reempaquetar la candidata

Para reproducir los dos ZIP con el ejecutable cualificado, recupera ese archivo del instalable y ejecuta el empaquetador desde la raíz de estas fuentes:

```sh
unzip -p /ruta/canica-1.0.1-rc37-rg35xx-h.zip share/system/canica/bin/emulationstation > nativo/emulationstation
python3 -B knulli/39-canica/release.py nativo salida/canica-1.0.1-rc37.zip distribucion
```

## Probar el instalable

Desde la raíz de estas fuentes, ejecuta en la computadora `bash knulli/39-canica/release/tests/probar-servicio.sh /ruta/knulli-h700-rg35xx-h-scarab-20260511.img.gz /ruta/canica-1.0.1-rc37-rg35xx-h.zip nativo/herramientas/fat_extract.py`. El ensayo crea un entorno Linux ARM64 descartable, comprueba el cambio de ejecutable y prueba la decisión de reiniciar con respuestas HTTP simuladas.
