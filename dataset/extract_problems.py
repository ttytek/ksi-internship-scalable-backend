#!/usr/bin/env python3
"""
Pobiera wybrane problemy z deepmind/code_contests i zapisuje pełne dane jako JSON.
Obsługuje zarówno pojedyncze indeksy, jak i zakresy (np. 10-25).

Użycie:
  python extract_problems.py 0 5 10-20 42
  python extract_problems.py 100-150 --split validation --out-dir ./problems
"""

import argparse
import json
import re
from pathlib import Path

from datasets import load_dataset


def to_serializable(obj):
    """Konwertuje obiekty (numpy itd.) na czyste typy Pythona."""
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_serializable(v) for v in obj]
    if hasattr(obj, "item"):  # numpy scalar
        return obj.item()
    if hasattr(obj, "tolist"):
        return obj.tolist()
    return obj


def safe_filename(name: str) -> str:
    """Usuwa znaki niebezpieczne w nazwach plików."""
    return re.sub(r"[^\w\-.]+", "_", name or "unknown")[:100]


def parse_indices(raw_args):
    """
    Parsuje listę argumentów:
      - pojedyncze liczby: 5
      - zakresy: 10-20 (włącznie)
    Zwraca posortowaną listę unikalnych indeksów.
    """
    indices = set()
    for arg in raw_args:
        if "-" in arg:
            parts = arg.split("-", 1)
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                raise ValueError(f"Niepoprawny zakres: '{arg}' (oczekiwano np. 10-25)")
            start, end = int(parts[0]), int(parts[1])
            if start > end:
                start, end = end, start
            indices.update(range(start, end + 1))
        else:
            if not arg.isdigit():
                raise ValueError(f"Niepoprawny indeks: '{arg}'")
            indices.add(int(arg))
    return sorted(indices)


def main():
    parser = argparse.ArgumentParser(
        description="Wyciąga konkretne problemy (pojedyncze lub zakresy) z deepmind/code_contests"
    )
    parser.add_argument(
        "indices",
        nargs="+",
        help="Indeksy lub zakresy, np.: 0 5 10-20 42",
    )
    parser.add_argument(
        "--split",
        default="train",
        choices=["train", "validation", "test", "valid"],
        help="Split datasetu (domyślnie: train). 'valid' = 'validation'",
    )
    parser.add_argument(
        "--out-dir",
        default="extracted_problems",
        help="Katalog docelowy (domyślnie: extracted_problems)",
    )
    args = parser.parse_args()

    # Hugging Face używa "validation"
    split = "validation" if args.split in ("valid", "validation") else args.split

    try:
        indices = parse_indices(args.indices)
    except ValueError as e:
        print(f"Błąd: {e}")
        return

    if not indices:
        print("Nie podano żadnych indeksów.")
        return

    needed = set(indices)
    max_idx = max(indices)

    print(f"Ładowanie split='{split}' z deepmind/code_contests (streaming)...")
    print(f"Szukam {len(indices)} problemów (max indeks: {max_idx})")
    print("(streaming – nie pobiera całego datasetu na dysk)\n")

    # streaming=True → nie ściąga wszystkich 39 plików train (~7.6 GB)
    ds = load_dataset("deepmind/code_contests", split=split, streaming=True)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    selected = {}
    for i, example in enumerate(ds):
        if i in needed:
            selected[i] = example
            print(f"  znaleziono indeks {i}")
        if i >= max_idx:
            break  # nie ma sensu streamować dalej

    saved = 0
    for idx in indices:
        if idx not in selected:
            print(f"[!] Indeks {idx} poza zakresem datasetu – pomijam")
            continue

        problem = to_serializable(selected[idx])
        name = problem.get("name", "unknown")
        fname = f"{split}_{idx:05d}_{safe_filename(name)}.json"
        out_path = out_dir / fname

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(problem, f, ensure_ascii=False, indent=2)

        # krótkie podsumowanie
        sols = problem.get("solutions") or {}
        n_sol = len(sols.get("solution", [])) if isinstance(sols, dict) else 0
        tests = problem.get("public_tests") or {}
        n_pub = len(tests.get("input", [])) if isinstance(tests, dict) else 0
        priv = problem.get("private_tests") or {}
        n_priv = len(priv.get("input", [])) if isinstance(priv, dict) else 0
        gen = problem.get("generated_tests") or {}
        n_gen = len(gen.get("input", [])) if isinstance(gen, dict) else 0

        print(f"[+] {out_path.name}")
        print(f"    name: {name} | solutions: {n_sol} | tests: {n_pub}/{n_priv}/{n_gen}")
        saved += 1

    print(f"\nGotowe. Zapisano {saved} problemów do katalogu: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
