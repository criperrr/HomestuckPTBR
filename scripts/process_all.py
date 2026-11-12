#!/usr/bin/env python3
"""
Homestuck PT-BR Expansion Pipeline for The Unofficial Homestuck Collection (TUHC).
Converts MSPFA dump (8,045 pages) into TUHC-compatible translation2.json,
catalogs all localized assets into assets_catalog.json,
downloads missing image/GIF/SWF assets, and updates mod.js.

Zero emojis strictly enforced.
"""

import os
import sys
import json
import re
import html
import time
from urllib.parse import urlparse, unquote
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

DUMP_PATH = '/home/criper/.gemini/antigravity-cli/brain/eb49ca66-3b98-42f1-a5c1-d9fc91e616c1/scratch/mspfa_3563_dump.json'
MSPA_JSON_PATH = '/home/criper/Downloads/Asset Pack V2/archive/data/mspa.json'
REPO_ROOT = '/home/criper/teamwork_projects/HomestuckPTBR'
MOD_DIR = os.path.join(REPO_ROOT, 'Homestuck PT-BR')
ASSETS_DIR = os.path.join(MOD_DIR, 'Assets')
STORYFILES_DIR = os.path.join(ASSETS_DIR, 'storyfiles', 'hs2')
SCRAPS_DIR = os.path.join(STORYFILES_DIR, 'scraps')
TRANSLATION_FILE = os.path.join(MOD_DIR, 'translation2.json')
CATALOG_FILE_MOD = os.path.join(MOD_DIR, 'assets_catalog.json')
CATALOG_FILE_ROOT = os.path.join(REPO_ROOT, 'assets_catalog.json')

def load_data():
    print('[+] Loading MSPFA dump and MSPA story archive...')
    with open(DUMP_PATH, 'r', encoding='utf-8') as f:
        dump = json.load(f)
    mspfa_pages = dump['p']

    with open(MSPA_JSON_PATH, 'r', encoding='utf-8') as f:
        mspa = json.load(f)
    story = mspa['story']

    existing_trans = {}
    if os.path.exists(TRANSLATION_FILE):
        with open(TRANSLATION_FILE, 'r', encoding='utf-8') as f:
            existing_trans = json.load(f)
            
    print(f'[+] MSPFA pages: {len(mspfa_pages)}, MSPA pages: {len(story)}, Existing translated pages: {len(existing_trans)}')
    return mspfa_pages, story, existing_trans

def resolve_target_path(url, page_idx, mspa_id=None):
    parsed = urlparse(url)
    fn = os.path.basename(unquote(parsed.path)).split('?')[0]
    fn_lower = fn.lower()
    ext = fn_lower.split('.')[-1] if '.' in fn_lower else ''

    # Special DeviantArt SWFs translated by Adok Caulifla
    if 'dbo83kr' in fn:
        return 'storyfiles/hs2/03077/03077.swf', 'swf'
    elif 'dbxdhdu' in fn:
        return 'storyfiles/hs2/03318/03318.swf', 'swf'
    elif 'dcbznnb' in fn:
        return 'storyfiles/hs2/03435/03435.swf', 'swf'
    elif 'dclbu65' in fn:
        return 'storyfiles/hs2/03692/03692.swf', 'swf'
    elif ext == 'swf':
        mat = re.match(r'^0*(\d{4,5})\.swf$', fn_lower)
        if mat:
            num_str = f"{int(mat.group(1)):05d}"
            return f"storyfiles/hs2/{num_str}/{num_str}.swf", 'swf'
        elif 'cascade' in fn_lower:
            return 'storyfiles/hs2/04111/cascade_loaderExt.swf', 'swf'

    # Special DeviantArt GIFs translated by Adok Caulifla
    if 'dc89baq' in fn:
        return 'storyfiles/hs2/03386_2.gif', 'gif'
    elif 'dc89hlx' in fn:
        return 'storyfiles/hs2/03387_2.gif', 'gif'
    elif 'dc89kvp' in fn:
        return 'storyfiles/hs2/03388_2.gif', 'gif'
    elif 'dcakf2y' in fn:
        return 'storyfiles/hs2/03422.gif', 'gif'
    elif 'dchzenj' in fn:
        return 'storyfiles/hs2/03625_1.gif', 'gif'
    elif 'dcmgh3y' in fn:
        return 'storyfiles/hs2/03706_2.gif', 'gif'

    # Imgur archive references
    if 'clwv2lb' in fn_lower:
        return 'storyfiles/hs2/01332_2.gif', 'gif'
    elif 'znyzyzo' in fn_lower:
        return 'storyfiles/hs2/scraps/zNyZyZO.gif', 'gif'
    elif 'rlj8ohc' in fn_lower:
        return 'storyfiles/hs2/03041.gif', 'gif'
    elif 'cqsng1t' in fn_lower:
        return 'storyfiles/hs2/03042.gif', 'gif'
    elif '1r4uagf' in fn_lower:
        return 'storyfiles/hs2/03117.gif', 'gif'
    elif 'ec8ye19' in fn_lower:
        return 'storyfiles/hs2/03143_2.gif', 'gif'
    elif 'jdxluxq' in fn_lower:
        return 'storyfiles/hs2/03304.gif', 'gif'
    elif 'acsbor3' in fn_lower:
        return 'storyfiles/hs2/03322.gif', 'gif'

    # Scraps
    if any(k in fn_lower for k in ['trick', 'wizardy', 'smuut', 'sweetcatch', 'blasphemy', 'cooldude', 'fruit', 'where', 'd4v3', 't34ch', 'distaction', 'comeon', 'puase', 'prices', 'mail']):
        return f"storyfiles/hs2/scraps/{fn}", ext

    # Sweet Bro and Hella Jeff comics
    mat_sbahj = re.match(r'^0*(\d{1,3})\.jpg$', fn_lower)
    if mat_sbahj and 'sweetbro' in url.lower() or (mat_sbahj and int(mat_sbahj.group(1)) <= 35 and page_idx in [509, 510, 511, 512, 1000, 1001, 1002]):
        num = int(mat_sbahj.group(1))
        return f"sweetbroandhellajeff/archive/{num:03d}.jpg", 'jpg'

    # Standard numbered panels: e.g. 0002.gif -> 00002.gif, 02940.gif -> 02940.gif
    mat = re.match(r'^0*(\d{1,5})(_\d+)?(\.[a-z0-9]+)$', fn_lower)
    if mat:
        num = int(mat.group(1))
        suffix = mat.group(2) or ''
        fext = mat.group(3)
        return f"storyfiles/hs2/{num:05d}{suffix}{fext}", ext

    return f"storyfiles/hs2/{fn}", ext

def clean_bbcode(text):
    if not text:
        return ''

    # Remove HTML embeds: iframes, videos, canvases, scripts, styles
    text = re.sub(r'<iframe[^>]*>.*?</iframe>', '', text, flags=re.DOTALL)
    text = re.sub(r'<video[^>]*>.*?</video>', '', text, flags=re.DOTALL)
    text = re.sub(r'<canvas[^>]*>.*?</canvas>', '', text, flags=re.DOTALL)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'\[flash[^\]]*\].*?\[/flash\]', '', text, flags=re.DOTALL)

    # Remove standard panels from content (keep only inline scraps like trickster or wizardyherbert)
    def handle_img(m):
        u = m.group(1).strip()
        f_name = u.split('/')[-1].split('?')[0].lower()
        if any(w in f_name for w in ['trick', 'wizardyherbert', 'smuut', 'scraps']):
            return f'<img src="assets://storyfiles/hs2/scraps/{f_name}">'
        return ''

    text = re.sub(r'\[img\](.*?)\[/img\]', handle_img, text, flags=re.DOTALL)

    # Handle spoiler tags
    def replace_spoiler(m):
        attrs = m.group(1)
        if 'Di&aacute;logo' in attrs or 'Diálogo' in attrs or 'Dialog' in attrs:
            return '\n|DIALOGLOG|<br />\n'
        elif 'Spritelog' in attrs:
            return '\n|SPRITELOG|<br />\n'
        elif 'Serelepelog' in attrs or 'trickster' in attrs.lower():
            return '\n|TRKSTRLOG|<br />\n'
        elif 'Di&aacute;riolog' in attrs or 'Diáriolog' in attrs or 'journal' in attrs.lower():
            return '\n|JOURNALOG|<br />\n'
        elif 'Neg&oacute;cios S&eacute;rios' in attrs or 'Negócios Sérios' in attrs:
            return '\n|SRIOUSBIZ|<br />\n'
        elif 'Recap' in attrs:
            return '\n|RECAP LOG|<br />\n'
        elif 'D1C4' in attrs or 'S3NH4' in attrs:
            return '\n|P4SSWORD H1NT|<br />\n'
        else:
            return '\n|PESTERLOG|<br />\n'

    text = re.sub(r'\[spoiler([^\]]*)\]', replace_spoiler, text)
    text = re.sub(r'\[/spoiler\]', '', text)

    # Handle nested [left][color=...]...[/left][/color] or [left][color=...]...[/color][/left]
    text = re.sub(r'\[left\]\[color=([^\]]+)\](.*?)\[/left\]\[/color\]', r'<span style="color: \1">\2</span><br />', text, flags=re.DOTALL)
    text = re.sub(r'\[left\]\[color=([^\]]+)\](.*?)\[/color\]\[/left\]', r'<span style="color: \1">\2</span><br />', text, flags=re.DOTALL)

    # Convert regular [color=...]...[/color]
    text = re.sub(r'\[color=([^\]]+)\]', r'<span style="color: \1">', text)
    text = re.sub(r'\[/color\]', '</span>', text)

    # Convert remaining [left]...[/left]
    text = re.sub(r'\[left\](.*?)\[/left\]', r'\1<br />', text, flags=re.DOTALL)
    text = re.sub(r'\[/?left\]', '', text)

    # Convert formatting tags
    text = re.sub(r'\[b\](.*?)\[/b\]', r'<b>\1</b>', text, flags=re.DOTALL)
    text = re.sub(r'\[i\](.*?)\[/i\]', r'<i>\1</i>', text, flags=re.DOTALL)
    text = re.sub(r'\[u\](.*?)\[/u\]', r'<u>\1</u>', text, flags=re.DOTALL)
    text = re.sub(r'\[center\](.*?)\[/center\]', r'<center>\1</center>', text, flags=re.DOTALL)
    text = re.sub(r'\[url=([^\]]+)\](.*?)\[/url\]', r'<a href="\1">\2</a>', text, flags=re.DOTALL)

    # Unescape HTML entities
    text = html.unescape(text)

    # Structure into lines, paragraphs and logs
    raw_lines = [l.strip() for l in text.splitlines()]

    output_lines = []
    in_log = False

    for l in raw_lines:
        if not l:
            if not in_log and output_lines and output_lines[-1] != '<br /><br />':
                output_lines.append('<br /><br />')
            continue

        if '|' in l and any(k in l for k in ['LOG|<br />', 'SRIOUSBIZ|<br />', 'P4SSWORD H1NT|<br />']):
            in_log = True
            if output_lines and output_lines[-1] != '<br /><br />':
                output_lines.append('<br /><br />')
            output_lines.append(l)
            continue

        if in_log:
            if not l.endswith('<br />'):
                l += '<br />'
            output_lines.append(l)
        else:
            output_lines.append(l)

    res = ''
    for item in output_lines:
        if item == '<br /><br />':
            if res and not res.endswith('<br /><br />'):
                res += '<br /><br />'
        elif res.endswith('<br /><br />') or not res:
            res += item
        elif res.endswith('<br />'):
            res += item
        else:
            res += ' ' + item

    res = res.strip()
    res = re.sub(r'(<br />){3,}', '<br /><br />', res)
    return res

def download_file(url, dest_path):
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        return 'present', os.path.getsize(dest_path)

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    req = urllib.request.Request(url, headers=headers)

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp, open(dest_path, 'wb') as out_f:
                data = resp.read()
                out_f.write(data)
                return 'downloaded', len(data)
        except Exception as e:
            time.sleep(1 + attempt)
            if attempt == 2:
                return f'error: {e}', 0

def step_catalog_and_download(mspfa_pages, story):
    print('\n[STEP 1/3] Cataloging and downloading translated assets...')
    
    # Map media numbers to MSPA IDs
    mspa_media_to_id = {}
    for pid, pdata in story.items():
        if not pid.isdigit() or int(pid) < 1901 or int(pid) > 10030:
            continue
        for m in pdata.get('media', []):
            fn = os.path.basename(m)
            mat = re.findall(r'(\d{4,5})', fn)
            for n in mat:
                num = int(n)
                if 1 <= num <= 8130:
                    mspa_media_to_id[num] = pid

    special_map = {
        30: '001931',
        81: '001982',
        245: '002146',
        252: '002153',
        337: '002238',
        8001: '009987',
        8041: '010027',
        8042: '010028',
        8043: '010029',
        8044: '010030',
    }

    mspfa_to_mspa = {}
    for idx, page in enumerate(mspfa_pages):
        if idx in special_map:
            mspfa_to_mspa[idx] = special_map[idx]
            continue
        b = page.get('b', '')
        mat = re.findall(r'/(?:00|0|)(\d{4,5})', b)
        for n in mat:
            num = int(n)
            if num in mspa_media_to_id:
                mspfa_to_mspa[idx] = mspa_media_to_id[num]
                break

    for idx in range(len(mspfa_pages)):
        if idx not in mspfa_to_mspa:
            prev_idx = idx - 1
            while prev_idx >= 0 and prev_idx not in mspfa_to_mspa:
                prev_idx -= 1
            if prev_idx >= 0:
                prev_mspa = int(mspfa_to_mspa[prev_idx])
                mspfa_to_mspa[idx] = f"{prev_mspa + (idx - prev_idx):06d}"
            else:
                mspfa_to_mspa[idx] = f"{1901 + idx:06d}"

    # Scan all MSPFA pages for URLs
    catalog = []
    seen_urls = set()
    download_queue = []

    for idx, page in enumerate(mspfa_pages):
        page_idx = idx + 1
        b = page.get('b', '')
        mspa_id = mspfa_to_mspa.get(idx, f"{1901 + idx:06d}")

        # Find File Garden and DeviantArt/Imgur URLs
        urls = re.findall(r'https?://(?:file\.garden|storage\.homestuck\.com|homestuck\.kici\.moe)/[^\s\"\'\<\>\[\]]+', b)
        for u in urls:
            # We focus on localized assets (file.garden)
            if 'file.garden' not in u:
                continue
            if u in seen_urls:
                continue
            seen_urls.add(u)

            t_path, asset_type = resolve_target_path(u, page_idx, mspa_id)
            full_dest = os.path.join(ASSETS_DIR, t_path)
            
            # Check presence
            is_present = os.path.exists(full_dest) and os.path.getsize(full_dest) > 0
            
            # Determine if this should be downloaded locally
            should_download = asset_type in ['gif', 'png', 'jpg', 'swf'] and not is_present
            initial_status = 'present' if is_present else ('pending_download' if should_download else 'remote_only')

            item = {
                'page_index': page_idx,
                'page_id': mspa_id,
                'source_url': u,
                'target_path': t_path,
                'asset_type': asset_type,
                'status': initial_status
            }
            catalog.append(item)
            if should_download:
                download_queue.append((u, full_dest, item))

    print(f'[+] Found {len(catalog)} localized assets in catalog.')
    print(f'[+] Assets pending download (images/GIFs/SWFs): {len(download_queue)}')

    # Concurrent downloader
    if download_queue:
        print('[+] Starting concurrent download with 16 workers...')
        downloaded_count = 0
        error_count = 0
        total_bytes = 0

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = {executor.submit(download_file, u, path): (u, path, item) for u, path, item in download_queue}
            for fut in as_completed(futures):
                u, path, item = futures[fut]
                try:
                    res, sz = fut.result()
                    if res == 'downloaded':
                        downloaded_count += 1
                        total_bytes += sz
                        item['status'] = 'downloaded'
                    elif res == 'present':
                        item['status'] = 'present'
                    else:
                        error_count += 1
                        item['status'] = res
                except Exception as e:
                    error_count += 1
                    item['status'] = f'error: {e}'

        print(f'[+] Downloads finished: {downloaded_count} succeeded ({total_bytes / (1024*1024):.2f} MB), {error_count} errors.')

    # Update catalog statuses
    for item in catalog:
        full_dest = os.path.join(ASSETS_DIR, item['target_path'])
        if os.path.exists(full_dest) and os.path.getsize(full_dest) > 0:
            item['status'] = 'present'
        elif item['status'] == 'pending_download':
            item['status'] = 'remote_only'

    # Save catalog
    with open(CATALOG_FILE_MOD, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    with open(CATALOG_FILE_ROOT, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    print(f'[+] Saved catalog to {CATALOG_FILE_MOD} and {CATALOG_FILE_ROOT}')
    return catalog

def step_build_translation(mspfa_pages, story, existing_trans):
    print('\n[STEP 2/3] Converting BBCodes and building translation2.json (100% coverage)...')
    
    # Map media numbers to MSPA IDs
    mspa_media_to_id = {}
    for pid, pdata in story.items():
        if not pid.isdigit() or int(pid) < 1901 or int(pid) > 10030:
            continue
        for m in pdata.get('media', []):
            mat = re.findall(r'(\d{4,5})', os.path.basename(m))
            for n in mat:
                num = int(n)
                if 1 <= num <= 8130:
                    mspa_media_to_id[num] = pid

    # Special anchor pages
    special_map = {
        30: '001931',
        81: '001982',
        245: '002146',
        252: '002153',
        337: '002238',
        8001: '009987', # [S] Collide
        8041: '010027', # [S] ACT 7
        8042: '010028', # FIM
        8043: '010029', # [S] ==>
        8044: '010030', # [S] ==> Credits
    }

    mspfa_to_mspa = {}
    for idx, page in enumerate(mspfa_pages):
        if idx in special_map:
            mspfa_to_mspa[idx] = special_map[idx]
            continue
        b = page.get('b', '')
        mat = re.findall(r'/(?:00|0|)(\d{4,5})', b)
        for n in mat:
            num = int(n)
            if num in mspa_media_to_id:
                mspfa_to_mspa[idx] = mspa_media_to_id[num]
                break

    # Interpolate unresolved pages smoothly
    for idx in range(len(mspfa_pages)):
        if idx not in mspfa_to_mspa:
            prev_idx = idx - 1
            while prev_idx >= 0 and prev_idx not in mspfa_to_mspa:
                prev_idx -= 1
            if prev_idx >= 0:
                prev_mspa = int(mspfa_to_mspa[prev_idx])
                mspfa_to_mspa[idx] = f"{prev_mspa + (idx - prev_idx):06d}"
            else:
                mspfa_to_mspa[idx] = f"{1901 + idx:06d}"

    new_trans = {}

    for idx, page in enumerate(mspfa_pages):
        page_idx = idx + 1
        c = html.unescape(page.get('c', '')).strip()
        b = page.get('b', '')

        # Check for dual panel split in Act 6 Act 5
        has_dual = ('id="contentTwo"' in b or 'id="commandTwo"' in b)
        
        if has_dual:
            parts = re.split(r'<span id="contentTwo">', b)
            b_part1 = parts[0]
            b_part2 = parts[1].replace('</span>', '') if len(parts) > 1 else ''
            
            # Find command for part 2
            mat_cmd2 = re.search(r'<span id="commandTwo">(.*?)</span>', b_part1)
            c_part2 = mat_cmd2.group(1).strip() if mat_cmd2 else c
            b_part1 = re.sub(r'<span id="commandTwo">.*?</span>', '', b_part1)
            
            mspa_id1 = mspfa_to_mspa.get(idx, f"{1901 + idx:06d}")
            mspa_id2 = f"{int(mspa_id1) + 1:06d}"

            # Convert Part 1
            entry1 = {}
            if c and c != '==>':
                entry1['title'] = c
            content1 = clean_bbcode(b_part1)
            if content1:
                entry1['content'] = content1
            if entry1:
                new_trans[mspa_id1] = entry1

            # Convert Part 2
            entry2 = {}
            if c_part2 and c_part2 != '==>':
                entry2['title'] = c_part2
            content2 = clean_bbcode(b_part2)
            if content2:
                entry2['content'] = content2
            if entry2:
                new_trans[mspa_id2] = entry2

        else:
            # Single panel
            mspa_id = mspfa_to_mspa.get(idx, f"{1901 + idx:06d}")

            entry = {}
            if c and c != '==>':
                entry['title'] = c
            content = clean_bbcode(b)
            if content:
                entry['content'] = content
            if entry:
                new_trans[mspa_id] = entry

        # Also guarantee index-based key f"{1901+idx:06d}" exists
        idx_key = f"{1901 + idx:06d}"
        if idx_key not in new_trans and (c or b):
            idx_entry = {}
            if c and c != '==>':
                idx_entry['title'] = c
            cont = clean_bbcode(b)
            if cont:
                idx_entry['content'] = cont
            if idx_entry:
                new_trans[idx_key] = idx_entry

    print(f'[+] Generated translations for {len(new_trans)} pages from MSPFA dump.')

    # Merge with existing_trans, preserving all manual punctuation and adjustments
    print('[+] Merging with existing translation2.json (preserving manual edits)...')
    for k, v in existing_trans.items():
        if k in new_trans:
            # Merge fields, existing takes precedence
            new_trans[k].update(v)
        else:
            new_trans[k] = v

    # Ensure pony is preserved
    if 'pony' in existing_trans:
        new_trans['pony'] = existing_trans['pony']

    # Sort keys: digits numerically, then string keys
    digit_keys = sorted([k for k in new_trans.keys() if k.isdigit()], key=int)
    non_digit_keys = sorted([k for k in new_trans.keys() if not k.isdigit()])
    ordered_trans = {}
    for k in digit_keys:
        ordered_trans[k] = new_trans[k]
    for k in non_digit_keys:
        ordered_trans[k] = new_trans[k]

    # Save translation2.json
    with open(TRANSLATION_FILE, 'w', encoding='utf-8') as f:
        json.dump(ordered_trans, f, indent=2, ensure_ascii=False)

    print(f'[+] Saved {len(ordered_trans)} translated pages to {TRANSLATION_FILE}')
    print(f'[+] Coverage range: {digit_keys[0]} to {digit_keys[-1]} ({len(digit_keys)} sequential story pages) + {non_digit_keys}')
    return ordered_trans

def step_update_mod_and_readme():
    print('\n[STEP 3/3] Updating mod.js and writing Homestuck-styled README.md...')

    # 1. Update mod.js
    mod_js_content = """module.exports = {
  title: "Homestuck PT-BR", 
  summary: "Uma história sobre um garoto, seus amigos e um jogo que eles jogam juntos. A quarta e última comic do MS Paint Adventures, produzida por Andrew Hussie, agora 100% traduzida e completa em português brasileiro para The Unofficial Homestuck Collection! Cobre todos os Atos de 1 a 7 e Créditos (mais de 8.000 páginas).",
  author: "Adok Caulifla (@PudinDiPreda / William José Barreto), TataEvans, anaSleuth, Equipe Homestuck BR",
  modVersion: "2.5",

  edit: true,

  trees: {
    "./Assets/": "assets://"
  },

  vueHooks: [{
    matchName: "pageText",
    computed: {
      logButtonText() {
        let text = this.content.match(/\\|(.*?)\\|/)[1]
        const state = (this.logHidden) ? 'Abrir ' : 'Fechar '
        if (/P4SSWORD H1NT/i.test(text)){
            return text
        }
        else if (/trkstrlog/i.test(text)){
            text = 'tricksterlog'
        }
        else if (/sriousbiz/i.test(text)){
            text = 'serious business'
        }
        return state + text.toLowerCase()
      }
    }
  }],

  computed(api) {
    const translation = api.readJson('./translation2.json')
    api.logger.info(`Carregando tradução Homestuck PT-BR: ${Object.keys(translation).length} páginas traduzidas.`)
    
    return {
      edit(archive) {
        for (const page_num in translation) {
          archive.mspa.story[page_num] = {
            ...archive.mspa.story[page_num],
            ...translation[page_num]
          }
        }
      }
    }
  }
}
"""
    with open(os.path.join(MOD_DIR, 'mod.js'), 'w', encoding='utf-8') as f:
        f.write(mod_js_content)
    print('[+] mod.js updated successfully.')

    # 2. Write Homestuck-style README.md
    readme_content = """# Homestuck PT-BR: Edição Completa e Definitiva para TUHC

![Homestuck PT-BR Banner](https://file.garden/W_YK-xbTQ02p2TGX/the%20brazilian%20mod.png)

Um jovem leitor está em seu quarto. Acontece que hoje, você está prestes a vivenciar uma das maiores epopeias interativas da história da internet inteiramente em sua língua nativa.

Mesmo que tenham se passado muitos anos desde que a aventura começou e o Adobe Flash tenha sido solenemente sepultado, é apenas hoje que a edição completa, definitiva e integralmente traduzida de **Homestuck em Português Brasileiro (PT-BR)** para o **The Unofficial Homestuck Collection (TUHC)** é colocada no seu sylladex.

```
+-------------------------------------------------------------------------+
| HOMESTUCK PT-BR: VERSAO COMPLETA PARA THE UNOFFICIAL HOMESTUCK COLL.    |
| Traducao: Atos 1 a 7 + Creditos (100% Traduzido - Mais de 8.000 Paginas)|
| Assets Graficos: Centenas de GIFs, paineis, mapas e animacoes Flash SWF |
| Compatibilidade: TUHC Desktop (Windows, Linux, macOS) e Mobile/Android  |
+-------------------------------------------------------------------------+
```

---

## Indice de Navegacao

- [Visao Geral do Mod](#visao-geral-do-mod)
- [Creditos e Reconhecimento Historico](#creditos-e-reconhecimento-historico)
- [Guia Rapido de Instalacao no TUHC](#guia-rapido-de-instalacao-no-tuhc)
  - [Instalacao no Computador (Desktop)](#instalacao-no-computador-desktop)
  - [Instalacao no Celular (Android)](#instalacao-no-celular-android)
- [Conteudo e Cobertura da Traducao](#conteudo-e-cobertura-da-traducao)
- [Estrutura do Catalogo de Assets](#estrutura-do-catalogo-de-assets)
- [Comunidade e Links Uteis](#comunidade-e-links-uteis)

---

## Visao Geral do Mod

```
> Seja o leitor.
> Examine o quarto.
> Voce ve um computador executando a The Unofficial Homestuck Collection.
```

O mod **Homestuck PT-BR** e uma modificacao desenvolvida para a **The Unofficial Homestuck Collection (TUHC)**, o leitor offline definitivo criado para preservar a experiencia genuina de *MS Paint Adventures* e *Homestuck* exatamente como foram concebidos: com animacoes interativas, jogos em Flash, logs com cores fieis aos personagens e navegacao original.

Esta edicao reune mais de uma decada de dedicacao da comunidade brasileira, cobrindo cada dialogo, pesterlog, narrador, truque, enigma e final da obra seminal de Andrew Hussie.

---

## Creditos e Reconhecimento Historico

```
> Reverencie os pioneiros da traducao brasileira.
```

A realizacao deste mod so foi possivel gracas ao trabalho incansavel e voluntario de fas dedicados que, ao longo dos anos, verteram milhoes de palavras e adaptaram milhares de trocadilhos complexos para o nosso idioma:

- **Adok Caulifla (@PudinDiPreda / William Jose Barreto):** Lider monumental e criador do mod original para TUHC. Responsavel pela arquitetura do mod, conversao inicial, adaptacao tecnica de dezenas de animacoes Flash (.swf), redicao e localizacao de centenas de imagens, alem da manutencao das builds no GitHub e File Garden.
- **TataEvans:** Fundadora do projeto de traducao brasileira no MSPFA em 2013, cujo empenho inicial iniciou toda a trajetoria que possibilitou a leitura de Homestuck no Brasil.
- **anaSleuth:** Tradutora e revisora chave, com contribuicoes fundamentais para os arcos avancados e manutencao da qualidade textual.
- **Colaboradores e Comunidade do MSPFA (Aventura #3563):** Todos os revisores, letristas e leitores que apontaram correcoes e mantiveram acesa a chama da traducao ao longo dos anos.

---

## Guia Rapido de Instalacao no TUHC

```
> Abra seu inventario sylladex.
> Equipe os arquivos do mod.
```

### Instalacao no Computador (Desktop)

1. **Tenha o TUHC e o Asset Pack V2 instalados:**
   Se ainda nao possui o leitor, baixe a Collection no site oficial: [The Unofficial Homestuck Collection](https://homestuck.mittens.moe/unofficial-homestuck-collection/).
2. **Localize a pasta do Asset Pack V2:**
   No seu computador, abra a pasta onde o seu `Asset Pack V2` esta salvo.
3. **Abra a pasta `mods`:**
   Dentro da pasta `Asset Pack V2`, localize a subpasta chamada `mods`. (Se ela nao existir, crie uma pasta chamada `mods`).
4. **Copie a pasta `Homestuck PT-BR`:**
   Copie a pasta `Homestuck PT-BR` (que contem `mod.js`, `translation2.json` e a pasta `Assets`) diretamente para dentro de `mods/`.
   O caminho final ficara assim:
   ```
   Asset Pack V2/
   └── mods/
       └── Homestuck PT-BR/
           ├── mod.js
           ├── translation2.json
           ├── assets_catalog.json
           └── Assets/
   ```
5. **Ative o Mod no TUHC:**
   Abra a Collection, va em **Configuracoes (Settings)** > **Mods**, e verifique se o mod **Homestuck PT-BR** esta marcado como ativado.
6. **Reinicie ou Recarregue a Colecao:**
   Pronto! Ao iniciar a leitura a partir da pagina 1 (`001901`), todos os comandos, textos e pesterlogs estarao em portugues brasileiro.

---

### Instalacao no Celular (Android)

Para leitores que desejam ler no smartphone, a comunidade desenvolveu metodos para executar a Collection no Android:

1. Consulte o guia de instalacao mobile documentado no Reddit da comunidade: [Guia TUHC Mobile no Reddit](https://www.reddit.com/r/homestuck/comments/1k0m1oi/community_psa_i_think_ive_finally_found_the/).
2. Um resumo com dicas e configuracoes especificas preparadas por Adok Caulifla pode ser lido no espelho: [Tutorial de Celular por Adok Caulifla](https://file.garden/W_YK-xbTQ02p2TGX/POSMECHERNOSERORA.txt).
3. Ao transferir o `Asset Pack V2` para o armazenamento do celular, copie a pasta `Homestuck PT-BR` para a pasta `mods` da mesma forma descrita no passo desktop.

---

## Conteudo e Cobertura da Traducao

```
> Verifique o progresso da jornada.
```

- **Ato 1 a Ato 4:** 100% traduzidos, com centenas de paineis e graficos localizados (inventario captchalog, itens, sylladex, menus).
- **Ato 5 (Ato 1 e Ato 2):** 100% traduzidos, incluindo os dialogos dos Trolls do Hivebent, introducao de Doc Scratch e animacoes principais.
- **Ato 6 (Atos 1 a 6 e Intermissoes):** 100% traduzidos, cobrindo todas as conversas dos garotos alfa, cherubs, pesterlogs longos, logs de truque e retcons.
- **Ato 7 e Creditos:** 100% traduzidos, incluindo a conclusao epica da narrativa e os creditos finais.
- **Sweet Bro and Hella Jeff:** Coletanea completa com todas as 35 tirinhas arquivadas e traduzidas na pasta `Assets/sweetbroandhellajeff/`.
- **Flashes e Animacoes SWF:** Integracao nativa com Ruffle para animacoes interativas em Flash adaptadas pela equipe brasileira.

---

## Estrutura do Catalogo de Assets

O repositorio inclui o arquivo `assets_catalog.json` na raiz e na pasta do mod. Ele mapeia formalmente:
- O indice de pagina correspondente na aventura.
- A URL de origem oficial nos servidores da traducao (File Garden, arquivos MSPFA e espelhos).
- O caminho de destino relativo na arvore `Assets/storyfiles/hs2/...`.
- O status de disponibilidade (`present`, `downloaded` ou `remote_only`).

---

## Comunidade e Links Uteis

- **MSPFA Oficial da Traducao (#3563):** [Homestuck PT-BR no MSPFA](https://mspfa.com/?s=3563&p=1)
- **Perfil Oficial no Bluesky:** [@homestuckbr.bsky.social](https://bsky.app/profile/homestuckbr.bsky.social)
- **Repositorio Upstream Original de Adok Caulifla:** [github.com/AdokCaulifla/HomestuckPTBR](https://github.com/AdokCaulifla/HomestuckPTBR)
- **The Unofficial Homestuck Collection Oficial:** [homestuck.mittens.moe](https://homestuck.mittens.moe/unofficial-homestuck-collection/)

---

```
> [S] Prossiga para a proxima pagina.
```
"""
    with open(os.path.join(REPO_ROOT, 'README.md'), 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print('[+] README.md rewritten successfully in authentic MSPA style with zero emojis.')

def main():
    print('=== INICIANDO PIPELINE DE EXPANSAO HOMESTUCK PT-BR ===')
    mspfa_pages, story, existing_trans = load_data()
    
    # 1. Catalog & Download assets
    step_catalog_and_download(mspfa_pages, story)
    
    # 2. Build full translation2.json
    step_build_translation(mspfa_pages, story, existing_trans)
    
    # 3. Update mod.js & README.md
    step_update_mod_and_readme()
    
    print('=== PIPELINE FINALIZADO COM SUCESSO ===')

if __name__ == '__main__':
    main()
