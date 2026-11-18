// Email Worker de Cloudflare: entrega cada correo recibido al LIMS (Paso 4).
//
// Variables del Worker (Workers > Settings > Variables):
//   URL_ENTRANTE    https://email.grupovicaf.com/api/entrante/
//   SECRETO         (tipo «Secreto») el mismo valor de CORREO_WEBHOOK_SECRET del .env
//   RESPALDO        (opcional) dirección verificada en Email Routing a la que se
//                   reenvía el correo si el LIMS no responde, para no perderlo.
// El secreto NO va en este archivo ni en el repositorio.

const MAX_BYTES = 25 * 1024 * 1024; // límite de Cloudflare Email Workers

function hex(buffer) {
  return [...new Uint8Array(buffer)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function firmar(secreto, fecha, para, cuerpo) {
  const encabezado = new TextEncoder().encode(`${fecha}\n${para}\n`);
  const datos = new Uint8Array(encabezado.length + cuerpo.byteLength);
  datos.set(encabezado, 0);
  datos.set(new Uint8Array(cuerpo), encabezado.length);
  const clave = await crypto.subtle.importKey(
    'raw', new TextEncoder().encode(secreto), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'],
  );
  return hex(await crypto.subtle.sign('HMAC', clave, datos));
}

export default {
  async email(message, env) {
    if (message.rawSize > MAX_BYTES) {
      message.setReject('552 5.3.4 Mensaje demasiado grande');
      return;
    }
    const cuerpo = await new Response(message.raw).arrayBuffer();
    const para = message.to.trim().toLowerCase();
    const fecha = Math.floor(Date.now() / 1000).toString();
    try {
      const respuesta = await fetch(env.URL_ENTRANTE, {
        method: 'POST',
        headers: {
          'Content-Type': 'message/rfc822',
          'X-Vicaf-Fecha': fecha,
          'X-Vicaf-Para': para,
          'X-Vicaf-Firma': await firmar(env.SECRETO, fecha, para, cuerpo),
        },
        body: cuerpo,
      });
      if (respuesta.status === 404) {
        message.setReject('550 5.1.1 La dirección no existe');
        return;
      }
      if (respuesta.status === 413) {
        message.setReject('552 5.3.4 Mensaje demasiado grande');
        return;
      }
      if (!respuesta.ok) throw new Error(`LIMS respondió ${respuesta.status}`);
    } catch (error) {
      if (env.RESPALDO) {
        await message.forward(env.RESPALDO);
        return;
      }
      throw error; // el remitente recibe un error temporal y reintenta
    }
  },
};
