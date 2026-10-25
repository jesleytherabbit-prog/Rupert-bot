# Rupert Bramble · Magic Chef

Bot de Discord en Python: anuncia turnos mediante comandos, recuerda su cierre y conserva los datos en SQLite. No detecta publicaciones del foro automáticamente. Un turno vigente por servidor; /turno reemplaza la programación anterior.

## 1. Preparar Discord

Crear la aplicación en https://discord.com/developers/applications y añadirla al servidor con los scopes `bot` y `applications.commands`. Permisos: Ver canales, Enviar mensajes, Insertar enlaces. No requiere Administrador ni intents privilegiados.

Crear un rol Concursantes y asignarlo a los jugadores. Para que sus menciones notifiquen, permitir mencionar ese rol en su configuración. Las preferencias individuales de notificación también influyen. Dar acceso al canal de avisos al bot aunque sea privado.

En Ajustes de usuario → Avanzado, activar Modo desarrollador. Clic derecho en el servidor, canal de avisos y rol Concursantes → Copiar ID. Son los tres identificadores de .env.example. El token se obtiene en Bot → Restablecer token; NO compartirlo, pegarlo en chats ni subirlo a GitHub.

## 2. GitHub

Crear un repositorio y subir el contenido de esta carpeta, incluyendo los archivos .env.example y .gitignore. No subir .env, la carpeta data ni la base SQLite. GitHub aloja el código: este proyecto necesita un proceso en ejecución, no GitHub Pages. No incluye Actions programadas.

## 3. Prueba local (Python 3.11 o posterior)

Abrir una terminal dentro de esta carpeta:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

En Windows: `py -m venv .venv`, activar con `.venv\Scripts\activate` y copiar .env.example a .env desde el explorador. Completar .env con un editor y ejecutar:

```sh
python bot.py
```

Dejar el proceso abierto. Los comandos se sincronizan con el servidor configurado al arrancar. Si no aparecen, comprobar ID e instalación con applications.commands y volver a abrir Discord.

## 4. Comandos

- `/turno titulo:La caja misteriosa enlace:https://tu-foro.example/tema cierre:2026-11-10 21:00 recordatorio:24`
- `/plazo`: consulta privada del turno vigente.
- `/ampliar cierre:2026-11-12 21:00`: anuncia el nuevo cierre y reinicia el recordatorio. No edita el anuncio original.
- `/cancelar`: desactiva avisos pendientes; conserva mensajes e historial.

Las fechas de entrada usan la zona TIMEZONE (por defecto Córdoba, Argentina). Discord muestra las fechas publicadas en la zona local de cada lector. Recordatorio 0 desactiva el aviso previo, pero se mantiene el aviso de cierre. Si falta menos tiempo que el configurado, el recordatorio llegará en la siguiente revisión. Los comandos administrativos requieren Gestionar servidor, verificado también en el programa.

## 5. Alojamiento continuo

Usar un servicio que permita un proceso Python permanente o contenedores. Comando de instalación: `pip install -r requirements.txt`; arranque: `python bot.py`. Configurar las seis variables de .env.example en los secretos/variables del proveedor, sin subir .env. Se incluye Dockerfile como alternativa.

IMPORTANTE: montar un disco persistente y apuntar DATABASE_PATH a él (por ejemplo /data/rupert.sqlite3). Sin disco persistente los despliegues pueden borrar los turnos. Ejecutar UNA sola instancia para evitar avisos duplicados. No usar un servicio que suspenda el proceso si se necesitan avisos puntuales. El bot no sirve una página HTTP.

## Comportamiento y límites

Revisa cada 30 segundos. Tras una desconexión entrega el cierre pendiente al volver; omite recordatorios previos si el plazo ya terminó. Los errores de envío se registran y reintentan. No garantiza entrega exactamente una vez: un corte entre enviar un aviso y guardar su estado puede duplicarlo. Un fallo durante un comando puede dejar un anuncio publicado sin guardar: revisar el canal antes de repetir. /cancelar no anuncia la cancelación públicamente.

No se ha probado contra una cuenta real: es necesario un ensayo en el servidor con un turno de prueba. Comprobar publicación, mención del rol, /plazo, cambio de cierre, cancelación y persistencia al reiniciar. No elimina posts del foro ni calcula puntuaciones.

Referencia técnica: https://discordpy.readthedocs.io/en/stable/interactions/api.html
