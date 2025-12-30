# PDF Product Extractor

**Automatically extract cropped product images and configuration data from product PDFs using OCR and smart layout detection.**

Perfect for e-commerce, product catalogs, and inventory management.

## ✨ Key Features

- ✅ **Extracts cropped product images** (not full pages!)
- ✅ **OCR text detection** to identify configuration names (h1 headers)
- ✅ **Smart image-text association** for descriptive naming
- ✅ **Removes text from images** - only pure product photos
- ✅ **Generates structured JSON** with product hierarchy
- ✅ **Works with any product PDF** - completely agnostic
- ✅ **Batch processing** for multiple PDFs
- ✅ **Interactive mode** for manual refinement

## 🚀 Quick Start

### Installation

```bash
cd pdf-product-extractor
pip install -r requirements.txt

# Also requires tesseract OCR (macOS):
brew install tesseract
```

### Basic Usage

```bash
./extract.sh "path/to/product.pdf"
```

That's it! The tool will:
1. Extract the h1 header as configuration name (e.g., "TOP STITCHING")
2. Find and crop product images
3. Name images using configuration + description text
4. Generate JSON linking everything together

## 📊 What You Get

```
product_name_output/
├── images/
│   ├── TOP_STITCHING_15mm.png           ← Cropped product photo
│   ├── TOP_STITCHING_6mm.png            ← Another option
│   ├── COLLAR_Button_Down.png
│   └── ...
└── product_name.json                     ← Structured data
```

### JSON Structure

```json
{
  "product_name": "Product Name",
  "configurations": [
    {
      "name": "TOP STITCHING",              ← H1 from page
      "id": "config_20",
      "page": 20,
      "options": [
        {
          "id": "config_20_option_1",
          "name": "TOP STITCHING 1.5MM",    ← Text near image
          "image": "TOP_STITCHING_15MM.png" ← Cropped, no text in image
        }
      ]
    }
  ]
}
```

## 💡 Real Example

**Input:** `FW21 Men's - Flight.pdf` (26 pages)

**Command:**
```bash
./extract.sh ~/Downloads/"FW21 Men_s - Flight.pdf"
```

**Output:**
```
✓ Configurations: 26 (CLOSURE, COLLAR, TOP STITCHING, etc.)
✓ Product images extracted: 99 cropped images
✓ Each image named: Configuration_Description.png
```

## 📖 Advanced Usage

### Custom Output Directory
```bash
./extract.sh "product.pdf" "./my_output"
```

### Batch Processing
```bash
./extract.sh --batch "/path/to/pdf_folder"
```

### Python API
```python
from extract_final import SmartProductExtractor

extractor = SmartProductExtractor("product.pdf", "output_dir")
try:
    data = extractor.process()
    print(f"Extracted {len(data['configurations'])} configurations")
finally:
    extractor.close()
```

## 🛠 How It Works

1. **Page Rendering**: Converts PDF pages to high-resolution images
2. **OCR Extraction**: Uses Tesseract to extract all text with positioning
3. **Header Detection**: Finds the largest text in top 25% of page (h1)
4. **Smart Cropping**: Detects visual regions using horizontal projection
5. **Image Segmentation**: Splits pages by whitespace/dividers
6. **Text Association**: Links nearby text to each product image
7. **Intelligent Naming**: Creates descriptive filenames from config + description

## 📋 Requirements

- Python 3.7+
- PyMuPDF (PDF processing)
- OpenCV (image processing)
- Tesseract OCR (text extraction)
- Pillow (image handling)
- pytesseract (OCR wrapper)

## 🎯 Use Cases

- **E-commerce**: Extract product variants for online stores
- **Catalogs**: Convert PDF catalogs to web-ready images + data
- **Inventory**: Structure legacy product documentation
- **Automation**: Batch process entire product libraries

## 🔧 Troubleshooting

**No images extracted?**
- Ensure images are embedded (not just vector graphics)
- Try adjusting DPI in `extract_page_as_image()`

**Poor configuration names?**
- Check OCR quality (tesseract must be installed)
- Headers should be visually distinct (larger text)

**Images include text?**
- The tool crops based on visual density
- Text-heavy regions are automatically excluded

## 📂 Project Files

- `extract_final.py` - **Main extractor (recommended)**
- `extract_product.py` - Legacy basic extractor
- `extract_improved.py` - Intermediate version
- `extract_interactive.py` - Interactive mode
- `batch_extract.py` - Batch processor
- `extract.sh` - Convenient shell wrapper
- `example_usage.py` - CSV/HTML examples

## 📄 License

Free to use and modify for your needs.

---

**Status:** ✅ Production Ready  
**Tested:** FW21 Men's - Flight.pdf (99 images, 26 configurations)
# pdf-product-extractor
