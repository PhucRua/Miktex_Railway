#!/usr/bin/env python3
"""
Script test đơn giản cho TikZ API
"""

import requests
import json

def test_health(base_url):
    """Test health endpoint"""
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check: {data['status']}")
            print(f"   PDFLatex: {data.get('pdflatex', 'unknown')}")
            print(f"   ImageMagick: {data.get('imagemagick', 'unknown')}")
            print(f"   TikZ: {data.get('tikz', 'unknown')}")
            return True
        else:
            print(f"❌ Health check failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_compile(base_url):
    """Test compile endpoint với TikZ đơn giản"""
    tikz_code = r"\draw[thick] (0,0) circle (1.5);\node at (0,0) {Test};"
    
    try:
        response = requests.post(
            f"{base_url}/compile",
            json={
                "tikz_code": tikz_code,
                "output_format": "png",
                "dpi": 150
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            if data["success"]:
                print("✅ TikZ compilation: SUCCESS")
                print(f"   Image generated: {bool(data.get('png_base64'))}")
                return True
            else:
                print(f"❌ TikZ compilation failed: {data.get('message')}")
                return False
        else:
            print(f"❌ TikZ compilation error: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ TikZ compilation error: {e}")
        return False

def main():
    print("🧪 TikZ API Simple Test")
    print("=" * 40)
    
    # Nhập URL
    base_url = input("Nhập Railway app URL: ").strip()
    if not base_url.startswith("http"):
        base_url = "https://" + base_url
    
    print(f"\n🔗 Testing: {base_url}")
    print("-" * 40)
    
    # Test health
    health_ok = test_health(base_url)
    
    # Test compile nếu health OK
    if health_ok:
        compile_ok = test_compile(base_url)
        
        print("\n📊 Summary:")
        print("-" * 40)
        if health_ok and compile_ok:
            print("🎉 ALL TESTS PASSED! API is working perfectly!")
        else:
            print("⚠️ Some tests failed. Check logs above.")
    else:
        print("\n❌ Health check failed, skipping compile test.")

if __name__ == "__main__":
    main()
