"""python -m tacticai.training: build the synthetic datasets, train the engine models (xG, xPass, VAEP) and measure the
style and formation presets. One-off, offline work: the pipeline only loads the trained models (interpret/application/models.py)."""
import argparse
import json
import os

from .action_dataset import build as build_actions
from .measure_presets import measure, write_doc
from .shot_dataset import build as build_shots
from .train_models import train, train_vaep, train_xpass

MODELS = "src/tacticai/interpret/models"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m tacticai.training")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("shots", help="build the synthetic kick-candidate dataset (run inside the engine Docker image)")
    s.add_argument("--matches", type=int, default=8, help="full matches, seeds 1000..")
    s.add_argument("--situations", type=int, default=40, help="300-step situations, seeds 50000..")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--out", default="data/datasets/shots_v2")
    d = sub.add_parser("actions-dataset", help="build the VAEP action dataset (run inside the engine Docker image)")
    d.add_argument("--matches", type=int, default=8, help="full matches, seeds 2000..")
    d.add_argument("--situations", type=int, default=40, help="300-step situations, seeds 60000..")
    d.add_argument("--workers", type=int, default=4)
    d.add_argument("--out", default="data/datasets/actions_v1")
    t = sub.add_parser("train-xg", help="train the engine xG model on the shot dataset")
    t.add_argument("--data", default="data/datasets/shots_v2")
    t.add_argument("--out", default=f"{MODELS}/xg_v1.json")
    u = sub.add_parser("train-xpass", help="train the engine xPass model on the pass dataset")
    u.add_argument("--data", default="data/datasets/v3")
    u.add_argument("--out", default=f"{MODELS}/xpass_v1.json")
    v = sub.add_parser("train-vaep", help="train the engine VAEP models (scores, concedes) on the action dataset")
    v.add_argument("--data", default="data/datasets/actions_v1")
    v.add_argument("--out", default=f"{MODELS}/vaep_v1.json")
    m = sub.add_parser("measure", help="measurement gate: style/formation metrics over headless matches (engine image)")
    m.add_argument("--what", choices=["styles", "formations"], required=True)
    m.add_argument("--seeds", type=int, default=20)
    m.add_argument("--steps", type=int, default=900)
    m.add_argument("--out", help="default data/measure/<what>.json")
    m.add_argument("--doc", default="data/measure/presets.md")
    a = ap.parse_args(argv)
    if a.cmd == "shots":
        return print(json.dumps(build_shots(a.matches, a.situations, a.workers, a.out), indent=2))
    if a.cmd == "actions-dataset":
        return print(json.dumps(build_actions(a.matches, a.situations, a.workers, a.out), indent=2))
    if a.cmd == "train-xg":
        return print(json.dumps(train(a.data, a.out), indent=1))
    if a.cmd == "train-xpass":
        return print(json.dumps(train_xpass(a.data, a.out), indent=1))
    if a.cmd == "train-vaep":
        return print(json.dumps(train_vaep(a.data, a.out), indent=1))
    if a.cmd == "measure":
        out = a.out or f"data/measure/{a.what}.json"
        os.makedirs(os.path.dirname(out), exist_ok=True)
        measure(a.what, a.seeds, a.steps, out)
        write_doc(os.path.dirname(out), a.doc)
        print(f"done: {out} {a.doc}")
        return
