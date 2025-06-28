from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import uuid
import os
from fastapi.responses import FileResponse

app = FastAPI()

class TikzCode(BaseModel):
    code: str

@app.post("/tikz")
async def compile_tikz(tikz: TikzCode):
    unique_id = str(uuid.uuid4())
    tex_file = f"/tmp/{unique_id}.tex"
    pdf_file = f"/tmp/{unique_id}.pdf"

    tex_template = r"""
    \documentclass[tikz,border=2pt]{standalone}
    \usepackage{tikz}
    \begin{document}
    %s
    \end{document}
    """ % tikz.code

    with open(tex_file, "w") as f:
        f.write(tex_template)

    try:
        subprocess.run(["pdflatex", "-output-directory=/tmp", tex_file],
                       check=True, timeout=15, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=400, detail="Compilation failed")

    if not os.path.exists(pdf_file):
        raise HTTPException(status_code=500, detail="PDF not generated")

    return FileResponse(pdf_file, media_type='application/pdf', filename='tikz.pdf')

@app.get("/")
def home():
    return {"status": "TikZ Compiler is running!"}
