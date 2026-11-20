"""Formularios del ensayo de compresión: datos FOR-004 de la probeta
(HU-LIMS-11), equipos (HU-LIMS-12) y sesión de ensayo (HU-LIMS-13)."""
from decimal import Decimal

from django import forms
from django.utils import timezone

from .models import Equipo, MuestraDetalle, SesionEnsayo

CLASE_CAMPO = 'mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5 text-base bg-white'


def _estilar(form):
    for campo in form.fields.values():
        campo.widget.attrs.setdefault('class', CLASE_CAMPO)


class DatosProbetaForm(forms.ModelForm):
    class Meta:
        model = MuestraDetalle
        fields = [
            'codigo_cliente', 'elemento_estructural', 'fc_diseno',
            'fecha_fabricacion', 'edad_ensayo_dias', 'material', 'tipo_probeta',
        ]
        widgets = {
            'fecha_fabricacion': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fc_diseno': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'inputmode': 'decimal'}),
            'edad_ensayo_dias': forms.NumberInput(attrs={'min': '0', 'inputmode': 'numeric'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilar(self)
        self.fields['fc_diseno'].label = "f'c (kg/cm²)"
        self.fields['fecha_fabricacion'].label = "Fabricación"
        self.fields['edad_ensayo_dias'].label = "Edad (días)"

    def clean_fecha_fabricacion(self):
        fecha = self.cleaned_data.get('fecha_fabricacion')
        if fecha and fecha > timezone.localdate():
            raise forms.ValidationError("La fecha de fabricación no puede ser futura.")
        return fecha


class EquipoForm(forms.ModelForm):
    class Meta:
        model = Equipo
        fields = [
            'codigo', 'nombre', 'tipo', 'marca', 'modelo', 'serie',
            'fecha_calibracion', 'vence_calibracion', 'certificado', 'activo',
        ]
        widgets = {
            'fecha_calibracion': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'vence_calibracion': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilar(self)
        self.fields['activo'].widget.attrs['class'] = 'h-5 w-5 rounded border-slate-300'

    def clean(self):
        datos = super().clean()
        cal, vence = datos.get('fecha_calibracion'), datos.get('vence_calibracion')
        if cal and vence and vence < cal:
            self.add_error('vence_calibracion', "El vencimiento no puede ser anterior a la calibración.")
        return datos


class AbrirSesionForm(forms.ModelForm):
    class Meta:
        model = SesionEnsayo
        fields = ['fecha', 'temperatura_inicial', 'humedad_inicial'] + [c for c, _ in SesionEnsayo.EQUIPOS]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'temperatura_inicial': forms.NumberInput(attrs={'step': '0.1', 'inputmode': 'decimal'}),
            'humedad_inicial': forms.NumberInput(attrs={'step': '0.1', 'inputmode': 'decimal'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilar(self)
        hoy = timezone.localdate()
        self.fields['fecha'].widget.attrs['max'] = hoy.isoformat()
        etiquetas = dict(Equipo.TIPOS)
        for campo, tipo in SesionEnsayo.EQUIPOS:
            disponibles = Equipo.disponibles(tipo, hoy)
            self.fields[campo].queryset = disponibles
            self.fields[campo].label = etiquetas[tipo]
            self.fields[campo].empty_label = "Elige…"
            if not self.is_bound and disponibles.count() == 1:
                self.initial[campo] = disponibles.first().pk

    def clean_fecha(self):
        fecha = self.cleaned_data['fecha']
        if fecha > timezone.localdate():
            raise forms.ValidationError("La fecha no puede ser futura.")
        return fecha

    def clean(self):
        datos = super().clean()
        _validar_ambiente(self, datos, 'temperatura_inicial', 'humedad_inicial')
        fecha = datos.get('fecha')
        if fecha:
            for campo, _ in SesionEnsayo.EQUIPOS:
                equipo = datos.get(campo)
                if equipo and equipo.vencido(fecha):
                    self.add_error(campo, f"{equipo.codigo} tiene la calibración vencida para esa fecha.")
        return datos


class CerrarSesionForm(forms.ModelForm):
    class Meta:
        model = SesionEnsayo
        fields = ['temperatura_final', 'humedad_final']
        widgets = {
            'temperatura_final': forms.NumberInput(attrs={'step': '0.1', 'inputmode': 'decimal'}),
            'humedad_final': forms.NumberInput(attrs={'step': '0.1', 'inputmode': 'decimal'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilar(self)
        for campo in self.fields.values():
            campo.required = True

    def clean(self):
        datos = super().clean()
        _validar_ambiente(self, datos, 'temperatura_final', 'humedad_final')
        return datos


def _validar_ambiente(form, datos, campo_t, campo_hr):
    t, hr = datos.get(campo_t), datos.get(campo_hr)
    if t is not None and not (Decimal('-10') <= t <= Decimal('50')):
        form.add_error(campo_t, "La temperatura debe estar entre -10 y 50 °C.")
    if hr is not None and not (Decimal('0') <= hr <= Decimal('100')):
        form.add_error(campo_hr, "La humedad relativa debe estar entre 0 y 100 %.")
