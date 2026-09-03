#!/usr/bin/env python3
"""Diagnose residual filter drops: are they concentrated in MIXED-HEIGHT blocks
(body text + embedded verse) where a single block-level median height mis-bands
the small lines? Compares retained counts and attributes drops."""
import json, glob, sys, os
sys.path.insert(0, 'GLM-OCR'); sys.path.insert(0, 'tools')
from glmocr.utils.word_mapping import tokenize_words, align_words, filter_word_order
from word_map import extract_page_words, build_provider_map
from glmocr.parser_result.pipeline_result import _normalized_to_pts
import numpy as np, pymupdf
os.environ.setdefault("DOCTR_CACHE_DIR", "models/doctr")
from doctr.models import ocr_predictor

f = glob.glob('outputs/full_set/ASTELL_1704_Moderation_truly_Stated/*.pages.jsonl')[0]
lines = [json.loads(l) for l in open(f) if l.strip()]
body = [l for l in lines if len((l.get('text') or '').strip()) > 200]
sample = body[::max(1,len(body)//8)][:8]

pred = ocr_predictor(det_arch="fast_base", reco_arch="crnn_mobilenet_v3_small", pretrained=True).to("cuda").half()
pred.det_predictor.pre_processor.batch_size = 16
pred.reco_predictor.pre_processor.batch_size = 64
doc = pymupdf.open(lines[0]['source'])

tot_pre = tot_v1 = mixed_drops = uniform_drops = 0
for d in sample:
    page = doc[d['page_index']]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(300/72, 300/72))
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    res = pred([img])
    pw = extract_page_words(res.pages[0], pix.width, pix.height)
    prov = build_provider_map(pw, d['blocks'])
    rect = d.get('page_rect_pts')
    for b in d['blocks']:
        tokens = tokenize_words(b.get('text') or '')
        bl = prov.get(b['id'], [])
        if not bl: continue
        aligns = align_words(tokens, [w.get('text') or '' for w in bl])
        pre = []
        for tok, pidx in zip(tokens, aligns):
            if pidx is None: continue
            frags = bl[pidx[0]:pidx[1]]
            boxes=[w['box_2d'] for w in frags if isinstance(w.get('box_2d'),list)]
            if not boxes: continue
            mb=[min(x[0] for x in boxes),min(x[1] for x in boxes),max(x[2] for x in boxes),max(x[3] for x in boxes)]
            bb=b.get('bbox_2d')
            if bb and len(bb)==4:
                mb=[max(bb[0],mb[0]),max(bb[1],mb[1]),min(bb[2],mb[2]),min(bb[3],mb[3])]
                if mb[0]>=mb[2] or mb[1]>=mb[3]: continue
            wp=_normalized_to_pts(mb,rect)
            pre.append({'text':tok['token'],'start':tok['start'],'end':tok['end'],'bbox_pts':wp})
        post = filter_word_order(pre)
        tot_pre += len(pre); tot_v1 += len(post)
        hs = [w['bbox_pts'][3]-w['bbox_pts'][1] for w in pre]
        drops_here = len(pre)-len(post)
        if hs and max(hs)>=15 and min(hs)<=9:
            mixed_drops += drops_here
        else:
            uniform_drops += drops_here
print(f"raw matched={tot_pre} | after v1={tot_v1} | retained={tot_v1/max(1,tot_pre)*100:.1f}%")
print(f"drops in MIXED-height blocks: {mixed_drops} | in UNIFORM blocks: {uniform_drops}")
