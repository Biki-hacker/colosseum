import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.config import settings
from app.storage import make_storage

st = make_storage()
debates = st.list_debates(4)

for i, d in enumerate(debates[:3]):
    d_id = d.get("id")
    topic = d.get("topic")
    status = d.get("status")
    winner = d.get("winner")
    created = d.get("created_at")
    ended = d.get("ended_at")
    
    duration_str = "N/A"
    if created and ended:
        try:
            t0 = datetime.fromisoformat(created.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(ended.replace("Z", "+00:00"))
            duration_s = (t1 - t0).total_seconds()
            duration_str = f"{duration_s:.1f}s ({duration_s/60:.2f} min)"
        except Exception as e:
            duration_str = str(e)
            
    print("=" * 80)
    print(f"DEBATE #{i+1} [ID: {d_id}]")
    print(f"TOPIC: {topic}")
    print(f"STATUS: {status} | WINNER: {winner} | DURATION: {duration_str}")
    print(f"TIMESTAMPS: Started={created} -> Ended={ended}")
    
    turns = st.get_turns(d_id)
    print(f"TOTAL TURNS: {len(turns)}")
    
    for t in turns[:6]:
        pos = t.get("position")
        spk = t.get("speaker", "").upper()
        txt = t.get("text", "").strip()
        tok = t.get("tokens")
        print(f"  [{pos+1:02d}] {spk:9s} ({tok:2d} tok): {txt}")
        
    if len(turns) > 6:
        print(f"  ... [{len(turns)-8} intermediate turns] ...")
        for t in turns[-2:]:
            pos = t.get("position")
            spk = t.get("speaker", "").upper()
            txt = t.get("text", "").strip()
            tok = t.get("tokens")
            print(f"  [{pos+1:02d}] {spk:9s} ({tok:2d} tok): {txt}")
    print()
