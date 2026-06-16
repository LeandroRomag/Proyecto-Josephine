# BY Josephine — Login & Register (Django)

## Estructura

```
templates/
  accounts/
    login.html
    register.html
static/
  css/
    auth.css
```

## Instalación

1. Copiá `templates/accounts/` dentro de tu carpeta `templates/`.
2. Copiá `static/css/auth.css` dentro de tu carpeta `static/css/`.
3. En tu `base.html`, agregá el CSS:

```html
<link rel="stylesheet" href="{% static 'css/styles.css' %}">
<link rel="stylesheet" href="{% static 'css/auth.css' %}">
```

## URLs (`urls.py`)

```python
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html'
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register_view, name='register'),
    path('password-reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
]
```

## View de registro (`views.py`)

```python
from django.contrib.auth import login, get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from django import forms

User = get_user_model()

class RegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name  = forms.CharField(max_length=30, required=True)
    email      = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})
```

## Google OAuth (opcional)

El botón "Continuar con Google" usa `{% url 'social:begin' 'google-oauth2' %}`,
que viene del paquete `social-auth-app-django`. Si no lo necesitás, cambialo
por `href="#"` o eliminá el botón.
