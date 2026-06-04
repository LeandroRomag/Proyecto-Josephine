from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password

from users.models import User
from shipping.models import ShippingZone, PickupPoint
from promotions.models import Promotion


ARGENTINA_PROVINCES = [
    ('buenos_aires', 'Buenos Aires'),
    ('caba', 'Ciudad Autónoma de Buenos Aires'),
    ('catamarca', 'Catamarca'),
    ('chaco', 'Chaco'),
    ('chubut', 'Chubut'),
    ('cordoba', 'Córdoba'),
    ('corrientes', 'Corrientes'),
    ('entre_rios', 'Entre Ríos'),
    ('formosa', 'Formosa'),
    ('jujuy', 'Jujuy'),
    ('la_pampa', 'La Pampa'),
    ('la_rioja', 'La Rioja'),
    ('mendoza', 'Mendoza'),
    ('misiones', 'Misiones'),
    ('neuquen', 'Neuquén'),
    ('rio_negro', 'Río Negro'),
    ('salta', 'Salta'),
    ('san_juan', 'San Juan'),
    ('san_luis', 'San Luis'),
    ('santa_cruz', 'Santa Cruz'),
    ('santa_fe', 'Santa Fe'),
    ('santiago_del_estero', 'Santiago del Estero'),
    ('tierra_del_fuego', 'Tierra del Fuego'),
    ('tucuman', 'Tucumán'),
]


class SiteSearchForm(forms.Form):
    q = forms.CharField(required=False, max_length=120)
    category = forms.IntegerField(required=False)


class OrderLookupForm(forms.Form):
    email = forms.EmailField(
        max_length=255,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'tuemail@ejemplo.com'}),
        label='Correo electrónico',
    )


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        max_length=255,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'tuemail@ejemplo.com'}),
        label='Correo electrónico',
    )

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


class PasswordResetConfirmForm(forms.Form):
    new_password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Nueva contraseña'}),
        label='Nueva contraseña',
    )
    new_password_confirm = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Confirmar contraseña'}),
        label='Confirmar contraseña',
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_new_password(self):
        password = self.cleaned_data['new_password']
        validate_password(password, user=self.user)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('new_password')
        password_confirm = cleaned_data.get('new_password_confirm')

        if password and password_confirm and password != password_confirm:
            self.add_error('new_password_confirm', 'Las contraseñas no coinciden.')

        return cleaned_data


class FrontendLoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'tuemail@ejemplo.com', 'class': 'form-input'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Contraseña', 'class': 'form-input'})
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')

        if email and password:
            self.user_cache = authenticate(request=self.request, email=email, password=password)
            if self.user_cache is None:
                raise forms.ValidationError('Credenciales inválidas.')

        return cleaned_data

    def get_user(self):
        return self.user_cache


class FrontendRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'placeholder': 'Email', 'class': 'form-input'}))
    first_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Nombre', 'class': 'form-input'}))
    last_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Apellido', 'class': 'form-input'}))
    phone = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Teléfono', 'class': 'form-input'}))

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con este correo electrónico.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = None
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class AddToCartForm(forms.Form):
    variant_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    quantity = forms.IntegerField(min_value=1, initial=1)


class CartLineForm(forms.Form):
    quantity = forms.IntegerField(min_value=0)


class CheckoutForm(forms.Form):
    customer_name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Nombre y apellido'}))
    customer_email = forms.EmailField(max_length=255, widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Correo electrónico'}))
    phone = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Teléfono'}))
    delivery_method = forms.ChoiceField(
        choices=(
            ('shipping', 'Envío a domicilio'),
        ),
        widget=forms.RadioSelect,
        initial='shipping',
    )
    province = forms.ChoiceField(
        choices=[('', 'Seleccioná una provincia')] + ARGENTINA_PROVINCES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-input', 'id': 'id_province'}),
    )
    city = forms.CharField(
        max_length=120,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-input',
            'id': 'id_city',
        }),
    )
    shipping_zone = forms.ModelChoiceField(
        queryset=ShippingZone.objects.filter(is_active=True),
        empty_label='Seleccionar zona',
        required=False,
    )
    pickup_point = forms.ModelChoiceField(
        queryset=PickupPoint.objects.filter(is_active=True),
        empty_label='Seleccionar punto de retiro',
        required=False,
    )
    address = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Dirección completa'}),
    )
    latitude = forms.FloatField(required=False, widget=forms.HiddenInput())
    longitude = forms.FloatField(required=False, widget=forms.HiddenInput())
    promo_code = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Código promo'}),
    )
    payment_method = forms.ChoiceField(
        choices=(
            ('mercado_pago', 'Mercado Pago'),
        )
    )

    def clean(self):
        cleaned_data = super().clean()
        delivery_method = cleaned_data.get('delivery_method')
        address = (cleaned_data.get('address') or '').strip()
        province = (cleaned_data.get('province') or '').strip()
        city = (cleaned_data.get('city') or '').strip()
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')
        promo_code = (cleaned_data.get('promo_code') or '').strip().upper()

        if delivery_method == 'shipping':
            if not province:
                self.add_error('province', 'Seleccioná una provincia.')
            if not city:
                self.add_error('city', 'Seleccioná una ciudad.')
            if not address:
                self.add_error('address', 'La dirección es requerida para envío.')
            if latitude is None or longitude is None:
                self.add_error(None, 'Seleccioná un punto en el mapa para continuar.')

        if promo_code:
            promotion = Promotion.objects.filter(code__iexact=promo_code, is_deleted=False).first()
            if promotion is None:
                self.add_error('promo_code', 'El código promocional no existe o no está activo.')
            else:
                cleaned_data['promotion'] = promotion
                cleaned_data['promo_code'] = promo_code
        else:
            cleaned_data['promotion'] = None

        return cleaned_data
