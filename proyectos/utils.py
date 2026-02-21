from twilio.rest import Client
from django.conf import settings

def enviar_whatsapp_pdf(numero, url_pdf, id_recepcion):
    account_sid = 'TU_ACCOUNT_SID_REAL' 
    auth_token = 'TU_AUTH_TOKEN_REAL'
    
    client = Client(account_sid, auth_token)

    if not str(numero).startswith('51'):
        numero = f"51{numero}"

    mensaje = client.messages.create(
        from_='whatsapp:+14155238886', 
        body=f'Hola! VICAFPRO LAB te informa que se ha generado el Cargo de Recepción N° {id_recepcion}.',
        media_url=[url_pdf],
        to=f'whatsapp:+{numero}'
    )
    return mensaje.sid