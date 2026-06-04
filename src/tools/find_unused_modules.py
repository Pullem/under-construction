#!/usr/bin/env python3
# tools/find_unused_modules.py
import ast
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIRS = ["src", ""]  # passe an, falls dein Code in src/ liegt

def all_py_files(root):
	for p in root.rglob("*.py"):
		if ".venv" in p.parts or "site-packages" in p.parts:
			continue
		yield p.relative_to(root)

def module_name_from_path(path: Path):
	parts = list(path.with_suffix("").parts)
	return ".".join(parts)

def parse_imports(path: Path):
	try:
		tree = ast.parse(path.read_text(encoding="utf-8"))
	except Exception:
		return set()
	imports = set()
	for node in ast.walk(tree):
		if isinstance(node, ast.Import):
			for n in node.names:
				imports.add(n.name.split(".")[0])
		elif isinstance(node, ast.ImportFrom):
			if node.module:
				imports.add(node.module.split(".")[0])
	return imports

def build_graph(root):
	files = {p: module_name_from_path(p) for p in all_py_files(root)}
	name_to_path = {v: k for k, v in files.items()}
	graph = {k: set() for k in files.keys()}
	for relpath in files.keys():
		path = root / relpath
		imports = parse_imports(path)
		for imp in imports:
			# match by prefix to local modules
			for modname, modpath in name_to_path.items():
				if modname == imp or modname.startswith(imp + "."):
					graph[relpath].add(modpath)
	return graph, files

def reachable_from(entry_paths, graph):
	seen = set()
	stack = list(entry_paths)
	while stack:
		cur = stack.pop()
		if cur in seen:
			continue
		seen.add(cur)
		for neigh in graph.get(cur, []):
			if neigh not in seen:
				stack.append(neigh)
	return seen

def main():
	root = REPO_ROOT
	graph, files = build_graph(root)
	# find main.py candidates
	mains = [p for p in files.keys() if p.name == "main.py"]
	if not mains:
		print("Keine main.py im Repo gefunden. Bitte Pfad anpassen.")
		sys.exit(1)
	# falls mehrere mains: nimm die erste
	entry = mains[0]
	reachable = reachable_from([entry], graph)
	all_files = set(files.keys())
	unused = sorted(all_files - reachable)
	print(f"Repo root: {root}")
	print(f"Entry point: {entry}")
	print("\n--- Reachable (kurz) ---")
	for r in sorted(reachable):
		print(f"  {r}")
	print("\n--- Mögliche ungenutzte Dateien ---")
	for u in unused:
		print(f"  {u}")
	print("\nHinweis: Prüfe dynamische Imports, CLI‑Skripte, Tests und config/ separat.")

if __name__ == "__main__":
	main()
