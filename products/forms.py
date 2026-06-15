from django import forms

from .models import Category, Drop, Product


class DropAdminForm(forms.ModelForm):
    class Meta:
        model = Drop
        fields = ['name', 'release_date', 'image', 'description', 'is_active']
        widgets = {
            'release_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class ProductAdminForm(forms.ModelForm):
    gallery_image_1 = forms.ImageField(required=False, widget=forms.FileInput(attrs={'accept': 'image/*'}))
    gallery_image_2 = forms.ImageField(required=False, widget=forms.FileInput(attrs={'accept': 'image/*'}))
    gallery_image_3 = forms.ImageField(required=False, widget=forms.FileInput(attrs={'accept': 'image/*'}))
    gallery_image_4 = forms.ImageField(required=False, widget=forms.FileInput(attrs={'accept': 'image/*'}))
    gallery_image_5 = forms.ImageField(required=False, widget=forms.FileInput(attrs={'accept': 'image/*'}))
    gallery_image_6 = forms.ImageField(required=False, widget=forms.FileInput(attrs={'accept': 'image/*'}))
    gallery_image_7 = forms.ImageField(required=False, widget=forms.FileInput(attrs={'accept': 'image/*'}))
    gallery_image_8 = forms.ImageField(required=False, widget=forms.FileInput(attrs={'accept': 'image/*'}))
    gallery_image_9 = forms.ImageField(required=False, widget=forms.FileInput(attrs={'accept': 'image/*'}))
    gallery_image_10 = forms.ImageField(required=False, widget=forms.FileInput(attrs={'accept': 'image/*'}))
    
    drop = forms.ModelChoiceField(
        queryset=Drop.objects.filter(is_active=True),
        required=False,
        empty_label="Sin Drop asignado"
    )

    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'admin-multi-select', 'size': 3}),
    )

    class Meta:
        model = Product
        fields = ['name', 'sku', 'description', 'price', 'categories', 'drop']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Ej. Top manga larga Olivia'}),
            'sku': forms.TextInput(attrs={'placeholder': 'SKU-001'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Detalles, materiales, calce...'}),
            'price': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '38900'}),
        }
        


class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Ej. Vestidos'}),
        }


class ProductVariantForm(forms.ModelForm):
    class Meta:
        from .models import ProductVariant
        model = ProductVariant
        # we don't expose the FK 'color' directly in the form; instead use a color_hex helper field
        fields = ['size', 'stock']
        widgets = {
            'size': forms.TextInput(attrs={'placeholder': 'Ej. S / M / L / 38'}),
            'stock': forms.NumberInput(attrs={'min': 0}),
        }

    # helper field to let the admin reference a color by hex (or pick an existing one)
    color_hex = forms.CharField(required=True, widget=forms.TextInput(attrs={'placeholder': '#rrggbb'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # if editing an existing variant, populate the helper field with the linked color hex
        if self.instance and getattr(self.instance, 'color', None):
            try:
                self.fields['color_hex'].initial = self.instance.color.color_hex
            except Exception:
                pass