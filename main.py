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

# Template LaTeX với packages đầy đủ cho TikZ
LATEX_TEMPLATE = r"""
\documentclass[border=2pt]{{standalone}}
\usepackage{{tikz}}
\usepackage{{pgfplots}}
\usepackage{{amsmath}}
\usepackage{{amsfonts}}
\usepackage{{amssymb}}
\usepackage{{xcolor}}
\usepackage{{graphicx}}

% Load TikZ libraries phổ biến
\usetikzlibrary{{
    arrows,
    arrows.meta,
    decorations.pathmorphing,
    decorations.markings,
    backgrounds,
    positioning,
    fit,
    calc,
    patterns,
    shapes,
    shapes.geometric,
    shapes.misc,
    plotmarks,
    matrix,
    trees,
    automata,
    circuits,
    3d
}}

% Set pgfplots compatibility
\pgfplotsset{{compat=1.16}}

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
        # Chạy pdflatex với các options tối ưu
        result = subprocess.run([
            'pdflatex', 
            '-interaction=nonstopmode',
            '-halt-on-error',
            '-output-directory', temp_dir,
            latex_file
        ], capture_output=True, text=True, timeout=45)
        
        if result.returncode != 0:
            # Parse LaTeX log để tìm lỗi cụ thể
            log_file = os.path.join(temp_dir, "tikz.log")
            error_details = "Unknown LaTeX error"
            
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    log_content = f.read()
                    
                    # Tìm các lỗi phổ biến
                    if "! LaTeX Error:" in log_content:
                        lines = log_content.split('\n')
                        for i, line in enumerate(lines):
                            if "! LaTeX Error:" in line and i < len(lines) - 1:
                                error_details = line + " " + lines[i+1]
                                break
                    elif "! Undefined control sequence" in log_content:
                        error_details = "Undefined control sequence - có thể thiếu package hoặc library TikZ"
                    elif "! Package tikz Error:" in log_content:
                        error_details = "TikZ package error - kiểm tra syntax TikZ code"
                    elif "! Package pgfplots Error:" in log_content:
                        error_details = "PGFPlots error - kiểm tra plot syntax"
                    elif "library not found" in log_content.lower():
                        error_details = "TikZ library not found - thử bỏ một số usetikzlibrary"
                    elif result.stderr:
                        error_details = result.stderr[:300]
            
            raise Exception(f"LaTeX compilation failed: {error_details}")
        
        pdf_file = os.path.join(temp_dir, "tikz.pdf")
        if not os.path.exists(pdf_file):
            raise Exception("PDF file was not generated - check LaTeX syntax")
        
        return pdf_file
    
    except subprocess.TimeoutExpired:
        raise Exception("LaTeX compilation timeout (45s) - code quá phức tạp hoặc lỗi infinite loop")
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

def check_tex_installation():
    """Kiểm tra cài đặt TeX và packages"""
    info = {}
    
    try:
        # Kiểm tra pdflatex
        result = subprocess.run(['pdflatex', '--version'], capture_output=True, text=True, timeout=10)
        info['pdflatex'] = "available" if result.returncode == 0 else "not available"
        
        # Kiểm tra kpsewhich cho TikZ
        result = subprocess.run(['kpsewhich', 'tikz.sty'], capture_output=True, text=True, timeout=5)
        info['tikz_package'] = "found" if result.returncode == 0 else "not found"
        
        # Kiểm tra pgfplots
        result = subprocess.run(['kpsewhich', 'pgfplots.sty'], capture_output=True, text=True, timeout=5)
        info['pgfplots_package'] = "found" if result.returncode == 0 else "not found"
        
        # Kiểm tra một số TikZ libraries
        libraries = ['arrows', 'decorations', 'positioning', 'shapes']
        found_libraries = []
        for lib in libraries:
            try:
                result = subprocess.run(['kpsewhich', f'tikzlibrary{lib}.code.tex'], 
                                      capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    found_libraries.append(lib)
            except:
                pass
        
        info['tikz_libraries'] = found_libraries
        
        # Kiểm tra ImageMagick
        result = subprocess.run(['convert', '--version'], capture_output=True, text=True, timeout=5)
        info['imagemagick'] = "available" if result.returncode == 0 else "not available"
        
    except Exception as e:
        info['error'] = str(e)
    
    return info

@app.get("/")
async def root():
    return {
        "message": "TikZ Compiler API", 
        "version": "1.0.0",
        "build": "Ubuntu TeXLive (Stable)",
        "status": "running",
        "port": os.getenv("PORT", "8000"),
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
        tex_info = check_tex_installation()
        
        # Determine overall health
        critical_components = [
            tex_info.get('pdflatex') == 'available',
            tex_info.get('tikz_package') == 'found', 
            tex_info.get('imagemagick') == 'available'
        ]
        
        is_healthy = all(critical_components)
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "build_type": "Ubuntu TeXLive (Stable)",
            "port": os.getenv("PORT", "8000"),
            "ready": True,
            **tex_info
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "error": str(e),
            "ready": False,
            "port": os.getenv("PORT", "8000")
        }

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
    # Railway expects PORT environment variable
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
