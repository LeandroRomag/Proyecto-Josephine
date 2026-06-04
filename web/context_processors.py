import os
import re
from urllib.parse import quote_plus

from django.conf import settings

from core.models import SiteSettings
from products.models import Category
from core.models import SiteText


def _build_whatsapp_url(raw_value):
	if not raw_value:
		return ''
	digits = re.sub(r'\D+', '', raw_value)
	if not digits:
		return ''
	message = os.getenv('CONTACT_WHATSAPP_MESSAGE', '').strip()
	if message:
		return f'https://wa.me/{digits}?text={quote_plus(message)}'
	return f'https://wa.me/{digits}'


def global_categories(request):
	"""Expose categories to all templates for the header navigation.

	Returns a queryset of categories ordered by name.
	"""
	return {
		'global_categories': Category.objects.all().order_by('name')
	}


def global_whatsapp_contact(request):
	settings = SiteSettings.objects.first()
	raw_value = os.getenv('CONTACT_WHATSAPP', '') or (settings.contact_whatsapp if settings else '')
	# Decide whether to show the floating action buttons based on request.path
	# Patterns can be configured via `settings.SHOW_FABS_PATHS` as a list of path prefixes.
	default_patterns = ['/', '/shop', '/catalog', '/productos', '/tienda']
	patterns = getattr(settings, 'SHOW_FABS_PATHS', default_patterns)
	path = (request.path or '').lower()
	show_fabs = False
	for p in patterns:
		if not p:
			continue
		p = p.lower()
		if p == '/' and path == '/':
			show_fabs = True
			break
		if p != '/' and path.startswith(p):
			show_fabs = True
			break

	# Build a mapping of site texts for templates: access as `site_texts.KEY`
	site_texts_qs = SiteText.objects.all()
	site_texts = {st.key: st.text for st in site_texts_qs}

	return {
		'whatsapp_contact_url': _build_whatsapp_url(raw_value),
		'whatsapp_contact_label': os.getenv('CONTACT_WHATSAPP_LABEL', 'WhatsApp'),
		'whatsapp_contact_message': os.getenv('CONTACT_WHATSAPP_MESSAGE', 'Hola, quiero hacer una consulta.'),
		'show_fabs': show_fabs,
		'site_texts': site_texts,
	}