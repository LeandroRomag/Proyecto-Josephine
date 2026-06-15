import django_filters
from .models import Product, Drop


class ProductFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    category = django_filters.ModelChoiceFilter(
        field_name='categories',
        queryset=None
    )
    drop = django_filters.ModelChoiceFilter(
        field_name='drop',
        queryset=None
    )
    price_min = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    in_stock = django_filters.BooleanFilter(
        field_name='stock',
        method='filter_in_stock'
    )

    class Meta:
        model = Product
        fields = ['name', 'category', 'drop','price_min', 'price_max', 'in_stock']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Category
        self.filters['category'].extra['queryset'] = Category.objects.all()
        self.filters['drop'].extra['queryset'] = Drop.objects.all()

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__gt=0)
        return queryset
