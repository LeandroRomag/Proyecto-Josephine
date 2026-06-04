import json
import os
import time

from django.core.management.base import BaseCommand
from django.conf import settings

from shipping.views import _fetch_cities_for_province
from web.forms import ARGENTINA_PROVINCES


class Command(BaseCommand):
    help = 'Prefetch cities for all Argentina provinces and store as JSON cache.'

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, default=None, help='Output JSON file path')
        parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests (seconds)')
        parser.add_argument('--overpass-timeout', type=int, default=25, help='Overpass API timeout in seconds')
        parser.add_argument('--nominatim-timeout', type=int, default=6, help='Nominatim API timeout in seconds')
        parser.add_argument('--provinces', type=str, default=None, help='Comma-separated province labels to fetch (e.g. "Buenos Aires,La Rioja"). If omitted, fetches all provinces.')

    def handle(self, *args, **options):
        output = options.get('output')
        delay = float(options.get('delay') or 1.0)

        if not output:
            # default to project root shipping_cities.json
            output = os.path.join(getattr(settings, 'BASE_DIR', '.'), 'shipping_cities.json')

        # If output exists, load existing cache to merge updates; otherwise start fresh
        result = {}
        if os.path.exists(output):
            try:
                with open(output, 'r', encoding='utf-8') as fh:
                    result = json.load(fh) or {}
            except Exception:
                result = {}
        total = len(ARGENTINA_PROVINCES)
        overpass_timeout = int(options.get('overpass_timeout') or options.get('overpass-timeout') or 25)
        nominatim_timeout = int(options.get('nominatim_timeout') or options.get('nominatim-timeout') or 6)

        provinces_arg = (options.get('provinces') or '').strip()
        if provinces_arg:
            targets = [p.strip() for p in provinces_arg.split(',') if p.strip()]
            provinces = [(k, l) for (k, l) in ARGENTINA_PROVINCES if l in targets]
        else:
            provinces = ARGENTINA_PROVINCES

        total = len(provinces)

        for idx, (key, label) in enumerate(provinces, start=1):
            self.stdout.write(f'[{idx}/{total}] Fetching cities for: {label}')
            try:
                cities = _fetch_cities_for_province(label, overpass_timeout=overpass_timeout, nominatim_timeout=nominatim_timeout)
            except Exception as e:
                self.stderr.write(f'Error fetching {label}: {e}')
                cities = []

            result[label] = {
                'key': key,
                'label': label,
                'count': len(cities),
                'cities': cities,
            }

            # Be polite with external services
            time.sleep(delay)

        # write file (merge into existing if present)
        try:
            # merge: update keys for provinces we fetched
            with open(output, 'w', encoding='utf-8') as fh:
                json.dump(result, fh, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f'Wrote cache to: {output}'))
        except Exception as e:
            self.stderr.write(f'Failed writing cache file: {e}')
