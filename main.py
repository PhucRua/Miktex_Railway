from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import tempfile
import subprocess
import os
import shutil
import base64
from pathlib import Path
import asyncio
import uuid

app = FastAPI(
    title="TikZ Compiler API",
    description="API để biên dịch TikZ code thành PDF và PNG",
    version="1.0.0"
)

# CORS middleware để cho phép truy cập từ web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TikZRequest(BaseModel):
    tikz_code: str
    output_format: str = "png"  # png, pdf, both
    dpi: int = 300
    background: str = "white"  # white, transparent

class CompileResponse(BaseModel):
    success: bool
    message: str
    pdf_base64: str = None
    png_base64: str = None
    file_id: str = None

# Template LaTeX cơ bản
LATEX_TEMPLATE = r"""
\documentclass[border=2pt]{{standalone}}
\usepackage{{tikz}}
\usepackage{{amsmath}}
\usepackage{{amsfonts}}
\usepackage{{amssymb}}
\usetikzlibrary{{arrows,decorations.pathmorphing,backgrounds,positioning,fit,petri,calc,patterns,shapes,plotmarks}}

\begin{{document}}
\begin{{tikzpicture}}
{tikz_content}
\end{{tikzpicture}}
\end{{document}}
"""

def create_latex_file(tikz_code: str, temp_dir: str) -> str:
    """Tạo file LaTeX từ TikZ code"""
    latex_content = LATEX_TEMPLATE.format(tikz_content=tikz_code)
    latex_file = os.path.join(temp_dir, "tikz.tex")
    
    with open(latex_file, 'w', encoding='utf-8') as f:
        f.write(latex_content)
    
    return latex_file

def compile_latex_to_pdf(latex_file: str, temp_dir: str) -> str:
    """Biên dịch LaTeX thành PDF"""
    try:
        # Chạy pdflatex
        result = subprocess.run([
            'pdflatex', 
            '-interaction=nonstopmode',
            '-output-directory', temp_dir,
            latex_file
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            raise Exception(f"LaTeX compilation failed: {result.stderr}")
        
        pdf_file = os.path.join(temp_dir, "tikz.pdf")
        if not os.path.exists(pdf_file):
            raise Exception("PDF file was not generated")
        
        return pdf_file
    
    except subprocess.TimeoutExpired:
        raise Exception("LaTeX compilation timeout")
    except Exception as e:
        raise Exception(f"Compilation error: {str(e)}")

def convert_pdf_to_png(pdf_file: str, temp_dir: str, dpi: int = 300, background: str = "white") -> str:
    """Chuyển đổi PDF thành PNG"""
    try:
        png_file = os.path.join(temp_dir, "tikz.png")
        
        # Sử dụng ImageMagick convert
        cmd = [
            'convert',
            '-density', str(dpi),
            '-quality', '100',
        ]
        
        if background == "transparent":
            cmd.extend(['-background', 'transparent'])
        else:
            cmd.extend(['-background', background])
        
        cmd.extend([
            '-alpha', 'remove' if background != "transparent" else 'on',
            pdf_file,
            png_file
        ])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            raise Exception(f"PDF to PNG conversion failed: {result.stderr}")
        
        if not os.path.exists(png_file):
            raise Exception("PNG file was not generated")
        
        return png_file
    
    except subprocess.TimeoutExpired:
        raise Exception("PDF to PNG conversion timeout")
    except Exception as e:
        raise Exception(f"Conversion error: {str(e)}")

def file_to_base64(file_path: str) -> str:
    """Chuyển đổi file thành base64"""
    with open(file_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')

@app.get("/")
async def root():
    return {
        "message": "TikZ Compiler API", 
        "version": "1.0.0",
        "endpoints": {
            "/compile": "POST - Biên dịch TikZ code",
            "/health": "GET - Kiểm tra trạng thái",
            "/docs": "GET - API documentation"
        }
    }

@app.get("/health")
async def health_check():
    """Kiểm tra trạng thái của API và các dependency"""
    try:
        # Kiểm tra pdflatex
        result = subprocess.run(['pdflatex', '--version'], capture_output=True, text=True)
        pdflatex_available = result.returncode == 0
        
        # Kiểm tra ImageMagick convert
        result = subprocess.run(['convert', '--version'], capture_output=True, text=True)
        convert_available = result.returncode == 0
        
        return {
            "status": "healthy" if pdflatex_available and convert_available else "unhealthy",
            "pdflatex": "available" if pdflatex_available else "not available",
            "imagemagick": "available" if convert_available else "not available"
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.post("/compile", response_model=CompileResponse)
async def compile_tikz(request: TikZRequest):
    """Biên dịch TikZ code thành PDF và/hoặc PNG"""
    
    if not request.tikz_code.strip():
        raise HTTPException(status_code=400, detail="TikZ code không được để trống")
    
    # Tạo thư mục tạm
    temp_dir = tempfile.mkdtemp()
    file_id = str(uuid.uuid4())
    
    try:
        # Tạo file LaTeX
        latex_file = create_latex_file(request.tikz_code, temp_dir)
        
        # Biên dịch thành PDF
        pdf_file = compile_latex_to_pdf(latex_file, temp_dir)
        
        response_data = {
            "success": True,
            "message": "Biên dịch thành công",
            "file_id": file_id
        }
        
        # Xử lý output format
        if request.output_format in ["pdf", "both"]:
            pdf_base64 = file_to_base64(pdf_file)
            response_data["pdf_base64"] = pdf_base64
        
        if request.output_format in ["png", "both"]:
            png_file = convert_pdf_to_png(pdf_file, temp_dir, request.dpi, request.background)
            png_base64 = file_to_base64(png_file)
            response_data["png_base64"] = png_base64
        
        return CompileResponse(**response_data)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi biên dịch: {str(e)}")
    
    finally:
        # Dọn dẹp thư mục tạm
        try:
            shutil.rmtree(temp_dir)
        except:
            pass

@app.post("/compile-file")
async def compile_tikz_file(file: UploadFile = File(...)):
    """Upload file TikZ và biên dịch"""
    
    if not file.filename.endswith(('.tex', '.tikz', '.txt')):
        raise HTTPException(status_code=400, detail="File phải có đuôi .tex, .tikz hoặc .txt")
    
    try:
        content = await file.read()
        tikz_code = content.decode('utf-8')
        
        request = TikZRequest(tikz_code=tikz_code, output_format="both")
        return await compile_tikz(request)
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File không đúng định dạng UTF-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý file: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
