from django.core.management.base import BaseCommand

from core.models import SiteText


DEFAULT_SITE_TEXTS = {
    'marquee_text': 'ENVÍOS GRATIS A TODO EL PAÍS · 3 Y 6 CUOTAS SIN INTERÉS · HASTA 70% OFF · NUEVA COLECCIÓN ·',
    'hero_eyebrow': 'SOLO POR 3 DÍAS',
    'hero_headline': 'HOT <em>BY Josephine</em>',
    'hero_badge_1': 'Hasta 70% OFF',
    'hero_badge_2': '+ Envíos gratis',
    'footer_help_envois': 'Envíos y devoluciones',
    'footer_help_talles': 'Guía de talles',
    'product_badge_new_in': 'NUEVO IN',
    'product_badge_hot_sale': 'HOT SALE',
}


class Command(BaseCommand):
    help = 'Restaura los textos editables del sitio para que vuelvan a mostrarse en el admin.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Sobrescribe el texto actual en lugar de solo crear los faltantes.',
        )

    def handle(self, *args, **options):
        created = 0
        updated = 0

        for key, text in DEFAULT_SITE_TEXTS.items():
            site_text, was_created = SiteText.objects.get_or_create(
                key=key,
                defaults={'text': text, 'description': ''},
            )

            if was_created:
                created += 1
                continue

            if options['overwrite'] and site_text.text != text:
                site_text.text = text
                site_text.description = site_text.description or ''
                site_text.save(update_fields=['text', 'description'])
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Textos restaurados. Creados: {created}. Actualizados: {updated}.'
            )
        )