# CONCEDE Motor V3 — habilitación de Mailing con Microsoft 365

## Buzón autorizado
El remitente está fijado en `C@4msfts.com`. La aplicación valida la identidad de Microsoft Graph tanto al conectar como inmediatamente antes de cada envío.

## Microsoft Entra
Registrar una aplicación para CONCEDE Motor V3 o ampliar una aplicación existente autorizada. Agregar una URI de redirección de plataforma **Web** que coincida exactamente con la URL pública de la aplicación Streamlit (incluyendo ruta y barra final).

Permisos delegados de Microsoft Graph:
- `User.Read`
- `Mail.Send`

Conceder consentimiento conforme a las políticas del tenant. No usar permisos de aplicación. El módulo no lee la bandeja de entrada.

## Secretos de Streamlit Community Cloud
En Manage app → Settings → Secrets, configurar los valores sin publicarlos en GitHub:

```toml
DATABASE_URL = "postgresql://...neon.tech/...?...sslmode=require"

[mailing]
tenant_id = "TENANT_ID"
client_id = "APPLICATION_CLIENT_ID"
client_secret = "CLIENT_SECRET"
sender_mailbox = "C@4msfts.com"
workspace_id = "4msfts"
# Opcional; si se omite, la app deriva la URL activa de Streamlit.
redirect_uri = "https://URL-PUBLICA-REAL-DE-CONCEDE/"
```

Nunca enviar estos valores por chat ni incorporarlos al repositorio. Si se configura `redirect_uri`, registrar exactamente la misma URL en Entra. Si se omite, CONCEDE deriva la URL pública activa; esa URL también debe estar registrada en Entra.

La conexión Neon usa la misma variable `DATABASE_URL` que Radar, pero Mailing escribe exclusivamente en sus tablas propias: `mailing_contacts` y `mailing_campaigns`. No modifica las tablas de señales ni el motor de scoring. Si `DATABASE_URL` no está configurada, la aplicación puede operar en SQLite local, pero esa modalidad no garantiza persistencia compartida en Streamlit Cloud.

## Operación
1. Importar CSV con empresa, correo, contacto, fuente y autorizado.
2. Validar correo y fuente. Solo contactos con autorización afirmativa pueden seleccionarse.
3. Preparar campaña y guardar borrador.
4. Conectar Microsoft 365 con el buzón institucional.
5. Revisar contenido y lista completa de destinatarios.
6. Marcar aprobación expresa y pulsar Enviar campaña aprobada.

Contactos y borradores se guardan por `workspace_id`. Los correos se envían en BCC. El servicio vuelve a consultar la identidad del buzón inmediatamente antes de enviar y rechaza cualquier cuenta distinta de `C@4msfts.com`. El límite operativo por campaña es de 500 destinatarios. HTTP 202 significa que Graph aceptó la solicitud; no garantiza entrega final.

## Seguridad y límites
No hay lectura de bandeja, envíos automáticos ni envíos programados. Ningún correo se envía al importar contactos, redactar o guardar borradores. Los secretos y tokens no se guardan en el repositorio. La caché OAuth permanece en la sesión de Streamlit; no se persisten tokens de Microsoft 365 en Neon.
