# CONCEDE Motor V3 — habilitación de Mailing con Microsoft 365

## Buzón autorizado
El remitente del módulo queda fijado en `C@4msfts.com`. La autenticación es delegada y valida que la cuenta conectada corresponda exactamente a ese buzón.

## Microsoft Entra
Registrar una aplicación para CONCEDE Motor V3 o ampliar una aplicación existente autorizada. Agregar URI de redirección de plataforma Web:
`https://concede-motor-v3.streamlit.app/`

Permisos delegados de Microsoft Graph:
- `User.Read`
- `Mail.Send`

Conceder consentimiento conforme a las políticas del tenant. No usar permisos de aplicación en esta primera integración. El módulo no lee la bandeja de entrada.

## Secretos de Streamlit Community Cloud
En Manage app → Settings → Secrets, configurar sin publicar valores en GitHub:

```toml
[mailing]
tenant_id = "TENANT_ID"
client_id = "APPLICATION_CLIENT_ID"
client_secret = "CLIENT_SECRET"
sender_mailbox = "C@4msfts.com"
```

Nunca enviar estos valores por chat ni incorporarlos al repositorio.

## Operación
1. Importar CSV con empresa, correo, contacto, fuente y autorizado.
2. Validar correo y fuente. Solo contactos con autorización afirmativa pueden seleccionarse.
3. Preparar campaña y guardar borrador.
4. Conectar Microsoft 365 con el buzón institucional.
5. Revisar contenido y lista completa.
6. Marcar aprobación expresa y pulsar Enviar campaña aprobada.

Los destinatarios se colocan en BCC. HTTP 202 significa que Graph aceptó la solicitud; no garantiza entrega final.

## Límites de este piloto
Contactos y borradores viven en la sesión de Streamlit; aún no hay persistencia compartida. No hay lectura de bandeja, automatizaciones ni envíos programados. Ningún correo se envía al importar, redactar o guardar borradores.

## URI de redirección
`https://concede-motor-v3.streamlit.app/`
