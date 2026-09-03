#!/usr/bin/env python3
"""Dump exact drop transitions under the current adaptive filter."""
import json, glob, sys, os
sys.path.insert(0, 'GLM-OCR'); sys.path.insert(0, 'tools')
from glmocr.utils.word_mapping import tokenize_words, align_words
from word_map import extract_page_words, build_provider_map
from glmocr.parser_result.pipeline_result import _normalized_to_pts
import numpy as np, pymupdf
os.environ.setdefault("DOCTR_CACHE_DIR", "models/doctr")
from doctr.models import ocr_predictor

f = glob.glob('outputs/full_set/ASTELL_1704_Moderation_truly_Stated/*.pages.jsonl')[0]
lines = [json.loads(l) for l in open(f) if l.strip()]
body = [l for l in lines if len((l.get('text') or '').strip()) > 200]
sample = body[::max(1,len(body)//4)][:4]

pred = ocr_predictor(det_arch="fast_base", reco_arch="crnn_mobilenet_v3_small", pretrained=True).to("cuda").half()
pred.det_predictor.pre_processor.batch_size = 16
pred.reco_predictor.pre_processor.batch_size = 64
doc = pymupdf.open(lines[0]['source'])

shown = 0
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
            gy=(wp[1]+wp[3])/2; gx=(wp[0]+wp[2])/2; h=wp[3]-wp[1]
            pre.append({'t':tok['token'],'gx':gx,'gy':gy,'h':h})
        # replicate filter exactly with logging
        hs = sorted(w['h'] for w in pre)
        med_h = hs[len(hs)//2] if hs else 20.0
        y_tol = max(4.0, 0.55*med_h); x_tol = max(5.0, 0.60*med_h)
        cur=None; prev_x=None; prev_y=-1e9
        for w in pre:
            v=''
            if w['gy'] < prev_y - y_tol: v='Y-UP'
            elif cur is not None and abs(w['gy']-cur)<=y_tol:
                if prev_x is not None and w['gx'] < prev_x - x_tol: v='X-REG'
            else:
                cur=w['gy']; prev_x=None
            prev_y=max(prev_y,w['gy'])
            if v:
                shown+=1
                if shown<=18:
                    print(f"{v}: '{w['t'][:14]}' gx={w['gx']:6.1f} gy={w['gy']:6.1f} h={w['h']:4.1f} | anchor={cur} prev_x={prev_x} | page {d['page_number']} blk {b['id']} medh={med_h:.0f}")
            else:
                if cur is not None and abs(w['gy']-cur)<=y_tol: prev_x=w['gx']
print("total drops shown-cap:", shown)
