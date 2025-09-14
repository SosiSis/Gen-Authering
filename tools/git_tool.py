# tools/git_tool.py
import tempfile, os, shutil
from git import Repo

def clone_repo(repo_url: str, dest_dir: str = None):
    dest = dest_dir or tempfile.mkdtemp(prefix="repo_")
    Repo.clone_from(repo_url, dest)
    return dest

def list_files(root: str):
    out = []
    for r,_,fnames in os.walk(root):
        for f in fnames:
            out.append(os.path.relpath(os.path.join(r,f), root))
    return out
