from django import forms
from django.core.exceptions import ValidationError

from .models import Promotion


class PromotionAdminForm(forms.ModelForm):
    start_date = forms.DateTimeField(
        required=True,
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
    )
    end_date = forms.DateTimeField(
        required=False,
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
    )

    class Meta:
        model = Promotion
        fields = [
            'name',
            'description',
            'code',
            'discount_type',
            'discount_value',
            'max_discount_amount',
            'min_order_value',
            'start_date',
            'end_date',
            'is_active',
            'max_uses',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Ej. Hot sale verano'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Detalle de la promoción...'}),
            'code': forms.TextInput(attrs={'placeholder': 'HOTSALE10'}),
            'discount_value': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '10'}),
            'max_discount_amount': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '15000'}),
            'min_order_value': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '50000'}),
            'max_uses': forms.NumberInput(attrs={'placeholder': '100'}),
        }
        help_texts = {
            'name': 'Nombre interno de la promoción. Sirve para identificarla en el panel.',
            'code': 'Código promocional opcional. Si luego activamos canje en checkout, este será el texto que ingrese el cliente.',
            'discount_type': 'Porcentaje descuenta un % del subtotal. Monto fijo descuenta un valor exacto en pesos.',
            'discount_value': 'Si el tipo es porcentaje, aquí va el porcentaje. Si es monto fijo, aquí va el importe.',
            'max_discount_amount': 'Tope máximo a descontar. Solo aplica para descuentos porcentuales.',
            'min_order_value': 'El carrito debe superar este valor para que la promo aplique.',
            'start_date': 'Fecha y hora desde la cual la promoción queda activa.',
            'end_date': 'Fecha y hora en la que la promoción deja de aplicarse. Puede quedar vacío.',
            'is_active': 'Desactivala si querés dejarla cargada pero no usarla todavía.',
            'max_uses': 'Cantidad máxima de veces que puede usarse. Vacío = ilimitado.',
        }

    def clean_code(self):
        code = (self.cleaned_data.get('code') or '').strip().upper()
        if not code:
            return None

        existing = Promotion.all_objects.filter(code__iexact=code)
        if self.instance and self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError(
                f'Ya existe una promoción con el código "{code}". Usá otro código o editá la promoción existente.'
            )

        return code