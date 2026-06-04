from django.apps import apps
from django.core.management.color import no_style
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


class Command(BaseCommand):
    help = 'Elimina datos de todas las apps del negocio y preserva la app de usuarios por defecto.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Ejecuta la limpieza sin pedir confirmación.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra las tablas que se limpiarían sin modificar datos.',
        )
        parser.add_argument(
            '--include-framework',
            action='store_true',
            help='También limpia tablas de Django/auth; por defecto se preservan.',
        )

    def handle(self, *args, **options):
        preserve_apps = {'users'}
        preserve_prefixes = {'users_'}
        if not options['include_framework']:
            preserve_prefixes.update({'django_', 'auth_'})

        tables_to_clear = []

        for app_config in apps.get_app_configs():
            if app_config.label in preserve_apps:
                continue

            for model in app_config.get_models():
                table_name = model._meta.db_table
                if any(table_name == prefix or table_name.startswith(prefix) for prefix in preserve_prefixes):
                    continue
                tables_to_clear.append(table_name)

        tables_to_clear = sorted(set(tables_to_clear))

        if not tables_to_clear:
            self.stdout.write(self.style.SUCCESS('No hay tablas para limpiar.'))
            return

        self.stdout.write('Tablas que se limpiarán:')
        for table_name in tables_to_clear:
            self.stdout.write(f'  - {table_name}')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('Dry-run activo: no se hicieron cambios.'))
            return

        if not options['force']:
            confirmation = input('Escribí BORRAR para continuar: ').strip()
            if confirmation != 'BORRAR':
                raise CommandError('Operación cancelada por el usuario.')

        sql_flush = connection.ops.sql_flush(
            no_style(),
            tables=tables_to_clear,
            reset_sequences=True,
        )

        with transaction.atomic():
            with connection.cursor() as cursor:
                for statement in sql_flush:
                    cursor.execute(statement)

        self.stdout.write(self.style.SUCCESS(
            f'Limpieza completada. Tablas afectadas: {len(tables_to_clear)}.'
        ))