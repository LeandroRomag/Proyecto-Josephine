from shipping.views import _fetch_cities_for_province

print('Fetching La Rioja...')
cities = _fetch_cities_for_province('La Rioja')
print('Count:', len(cities))
for i,c in enumerate(cities[:10]):
    print(i+1, c.get('name'), c.get('lat'), c.get('lng'))
