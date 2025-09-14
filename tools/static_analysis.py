# tools/static_analysis.py
import os, ast

def extract_metrics(repo_path: str):
    metrics = {"num_files": 0, "num_py": 0, "top_functions": []}
    for r,_,fnames in os.walk(repo_path):
        for f in fnames:
            metrics["num_files"] += 1
            if f.endswith(".py"):
                metrics["num_py"] += 1
                p = os.path.join(r, f)
                try:
                    tree = ast.parse(open(p, 'r', encoding='utf-8').read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            metrics["top_functions"].append(node.name)
                except Exception:
                    pass
    metrics["top_functions"] = metrics["top_functions"][:30]
    return metrics
