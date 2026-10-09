#!/usr/bin/env python3
"""Public, credential-free version of the bridge's marketplace helper.

Results come from the live public API; no dated illustrative offers are used.
Telegram upload is optional and requires credentials in the process environment.
"""
import argparse
import io
import json
import os
from pathlib import Path
import tempfile
import urllib.parse
import urllib.request
from PIL import Image, ImageDraw


def search(query):
    url = 'https://gateway.chotot.com/v1/public/ad-listing?' + urllib.parse.urlencode({'q': query, 'limit': 20})
    request = urllib.request.Request(url, headers={'User-Agent': 'Vivian marketplace helper'})
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.load(response)
    results = []
    for ad in data.get('ads', []):
        if not ad.get('list_id') or not isinstance(ad.get('price'), (int, float)) or ad['price'] <= 0:
            continue
        results.append({
            'model': ad.get('subject', 'Unknown variant'), 'price': ad['price'],
            'seller': ad.get('account_name', 'Unknown seller'),
            'location': ', '.join(str(ad[k]) for k in ('area_name', 'region_name') if ad.get(k)),
            'url': 'https://www.chotot.com/' + str(ad['list_id']) + '.htm',
        })
    return sorted(results, key=lambda row: row['price'])


def chart(rows, query):
    image = Image.new('RGB', (1000, 80 + len(rows) * 60), (20, 22, 28))
    draw = ImageDraw.Draw(image)
    draw.text((20, 15), query, fill='white')
    maximum = max(row['price'] for row in rows)
    for i, row in enumerate(rows):
        y = 60 + i * 60
        draw.text((20, y), row['model'][:100], fill='white')
        width = int(row['price'] / maximum * 700)
        draw.rectangle((20, y + 20, 20 + width, y + 35), fill=(103, 212, 228))
        draw.text((750, y + 20), f"{row['price']:,.0f} VND", fill='white')
    directory = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'vivian'
    directory.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix='gpu-listings-', suffix='.png', dir=directory)
    with os.fdopen(fd, 'wb') as out:
        image.save(out, 'PNG')
    return Path(filename)


def send_telegram(path, query):
    token, chat = os.environ.get('TELEGRAM_BOT_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat:
        raise ValueError('Telegram upload requires private environment credentials; none are included in Vivian.')
    boundary = 'Vivian' + os.urandom(16).hex()
    payload = bytearray()
    for name, value in (('chat_id', chat), ('caption', query)):
        payload.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    payload.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="comparison.png"\r\nContent-Type: image/png\r\n\r\n'.encode())
    payload.extend(path.read_bytes())
    payload.extend(f'\r\n--{boundary}--\r\n'.encode())
    request = urllib.request.Request('https://api.telegram.org/bot' + token + '/sendPhoto', data=bytes(payload), headers={'Content-Type': 'multipart/form-data; boundary=' + boundary})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.load(response)
    except Exception:
        raise RuntimeError('Telegram upload failed; secret URL withheld.') from None
    if result.get('ok') is not True:
        raise RuntimeError('Telegram rejected upload; secret response withheld.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query')
    parser.add_argument('--send-telegram', action='store_true', help='Explicitly upload using private environment credentials.')
    args = parser.parse_args()
    rows = search(args.query)
    if not rows:
        print('No concrete priced listings were returned. No prices were invented.')
        return
    print('| Variant | Seller | Price (VND) | Location | Source |')
    print('|---|---|---:|---|---|')
    for row in rows:
        clean = lambda value: str(value).replace('|', '/').replace('\n', ' ')
        print(f"| {clean(row['model'])} | {clean(row['seller'])} | {row['price']:,.0f} | {clean(row['location'])} | {row['url']} |")
    path = chart(rows[:10], args.query)
    print('Chart saved: ' + str(path))
    if args.send_telegram:
        send_telegram(path, args.query)
        print('Telegram upload independently acknowledged by the API.')


if __name__ == '__main__':
    main()
