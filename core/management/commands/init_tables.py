from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Crea migraciones y aplica migrate para inicializar todas las tablas del proyecto.'

    def handle(self, *args, **options):
        apps = ['users', 'products', 'orders', 'shipping', 'payments', 'cart', 'promotions', 'core']
        self.stdout.write('Creando migraciones para apps: ' + ', '.join(apps))
        call_command('makemigrations', *apps)
        self.stdout.write('Aplicando migraciones...')
        call_command('migrate')
        self.stdout.write(self.style.SUCCESS('Tablas inicializadas correctamente.'))
