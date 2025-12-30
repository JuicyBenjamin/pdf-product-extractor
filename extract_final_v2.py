#!/usr/bin/env python3
"""
Final PDF Product Extractor
- Proper folder structure per configuration
- Better padding for images
- Full text descriptions
- Arrow/zoom detection
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
import pymupdf as fitz
import cv2
import numpy as np
import pytesseract


class FinalProductExtractor:
    def __init__(self, pdf_path: str, output_dir: str = None):
        self.pdf_path = Path(pdf_path)
        self.output_dir = Path(output_dir) if output_dir else self.pdf_path.parent / f"{self.pdf_path.stem}"
        self.output_dir.mkdir(exist_ok=True)
        self.images_dir = self.output_dir / "images"
        self.images_dir.mkdir(exist_ok=True)
        
        self.doc = fitz.open(str(self.pdf_path))
        self.product_name = self.pdf_path.stem
        
    def extract_page_as_image(self, page_num: int, dpi: int = 200) -> np.ndarray:
        """Convert PDF page to image"""
        page = self.doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    
    def extract_text_with_ocr(self, img: np.ndarray) -> List[Dict[str, Any]]:
        """Extract text using OCR"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ocr_data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
        
        text_blocks = []
        n_boxes = len(ocr_data['text'])
        
        for i in range(n_boxes):
            text = ocr_data['text'][i].strip()
            conf = int(ocr_data['conf'][i])
            
            if text and conf > 20:
                x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
                text_blocks.append({
                    'text': text,
                    'bbox': (x, y, x + w, y + h),
                    'confidence': conf,
                    'font_size': h
                })
        
        return text_blocks
    
    def find_configuration_name(self, text_blocks: List[Dict[str, Any]], img_height: int) -> str:
        """Find the main header/configuration name"""
        if not text_blocks:
            return None
        
        # Build lines from words
        lines = {}
        for block in text_blocks:
            y = block['bbox'][1]
            line_key = y // 20
            if line_key not in lines:
                lines[line_key] = []
            lines[line_key].append(block)
        
        # Combine words into lines
        text_lines = []
        for line_key in sorted(lines.keys()):
            sorted_words = sorted(lines[line_key], key=lambda x: x['bbox'][0])
            line_text = ' '.join(w['text'] for w in sorted_words)
            avg_size = sum(w['font_size'] for w in sorted_words) / len(sorted_words)
            y_pos = sorted_words[0]['bbox'][1]
            
            text_lines.append({
                'text': line_text,
                'font_size': avg_size,
                'y': y_pos
            })
        
        # Find largest text in top 30% of page
        top_section = img_height * 0.3
        candidates = [l for l in text_lines if l['y'] < top_section and len(l['text']) > 3]
        
        if candidates:
            header = max(candidates, key=lambda x: x['font_size'])
            return header['text'].strip()
        
        return None
    
    def detect_arrows_or_zoom(self, img_region: np.ndarray) -> bool:
        """
        Detect if image contains an arrow graphic (typically pointing right between two images).
        This indicates a zoom/detail relationship.
        Very conservative detection - only flag obvious arrows.
        """
        gray = cv2.cvtColor(img_region, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        
        # Arrow graphics are typically in a narrow vertical band in the center
        center_y1 = int(height * 0.35)
        center_y2 = int(height * 0.65)
        center_x1 = int(width * 0.40)
        center_x2 = int(width * 0.60)
        
        center_region = gray[center_y1:center_y2, center_x1:center_x2]
        
        # Threshold to find dark arrow graphics on light background
        _, binary = cv2.threshold(center_region, 200, 255, cv2.THRESH_BINARY_INV)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Arrow graphics are small, distinct shapes
            # Too small = noise, too large = not an arrow
            if 200 < area < 3000:
                # Get convex hull to check shape
                hull = cv2.convexHull(contour)
                hull_area = cv2.contourArea(hull)
                
                if hull_area == 0:
                    continue
                
                # Solidity = how "solid" the shape is (arrow should be fairly solid)
                solidity = area / hull_area
                
                if solidity > 0.6:
                    # Check aspect ratio
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = w / float(h) if h > 0 else 0
                    
                    # Arrows pointing right are wider than tall
                    # Be very strict: must be clearly horizontal
                    if 1.5 < aspect_ratio < 3.5:
                        # Additional check: the arrow should be relatively small
                        # compared to the region (not a full product image)
                        region_area = center_region.shape[0] * center_region.shape[1]
                        if area < region_area * 0.15:  # Arrow is less than 15% of center region
                            return True
        
        return False
    
    def extract_images_between_text(self, img: np.ndarray, text_blocks: List[Dict[str, Any]]) -> List[Tuple[np.ndarray, str, bool]]:
        """
        Extract product images between text labels.
        Returns: (cropped_image, label_text, has_arrow)
        """
        height, width = img.shape[:2]
        
        # Group text blocks into lines
        lines = {}
        for block in text_blocks:
            y_center = (block['bbox'][1] + block['bbox'][3]) / 2
            line_key = int(y_center // 30)
            if line_key not in lines:
                lines[line_key] = []
            lines[line_key].append(block)
        
        # Combine words in each line
        text_lines = []
        for line_key in sorted(lines.keys()):
            blocks_in_line = sorted(lines[line_key], key=lambda x: x['bbox'][0])
            line_text = ' '.join(b['text'] for b in blocks_in_line)
            
            y_min = min(b['bbox'][1] for b in blocks_in_line)
            y_max = max(b['bbox'][3] for b in blocks_in_line)
            
            text_lines.append({
                'text': line_text,
                'y_min': y_min,
                'y_max': y_max,
                'y_center': (y_min + y_max) / 2
            })
        
        # Find image regions (gaps between text)
        image_regions = []
        
        if not text_lines:
            return []
        
        for i in range(len(text_lines)):
            current_text_end = text_lines[i]['y_max'] + 20
            
            if i < len(text_lines) - 1:
                next_text_start = text_lines[i+1]['y_min'] - 20
            else:
                next_text_start = height
            
            gap_height = next_text_start - current_text_end
            min_gap = height * 0.06
            
            if gap_height > min_gap:
                label = text_lines[i]['text']
                image_regions.append((int(current_text_end), int(next_text_start), label))
        
        # Extract and validate each image region
        product_images = []
        
        for y1, y2, label in image_regions:
            if y2 - y1 < 30:
                continue
            
            region_img = img[y1:y2, :]
            
            # More generous padding when trimming
            cropped = self.trim_whitespace(region_img, padding=25)
            
            if cropped is None or cropped.shape[0] < 50 or cropped.shape[1] < 50:
                continue
            
            gray_crop = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            std_dev = np.std(gray_crop)
            
            edges = cv2.Canny(gray_crop, 50, 150)
            edge_ratio = np.sum(edges > 0) / edges.size
            
            if std_dev > 8 and edge_ratio < 0.15:
                has_arrow = self.detect_arrows_or_zoom(cropped)
                product_images.append((cropped, label, has_arrow))
        
        return product_images
    
    def trim_whitespace(self, img: np.ndarray, padding: int = 25) -> np.ndarray:
        """Trim whitespace with generous padding"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # More lenient threshold for content detection
        row_has_content = np.sum(gray < 250, axis=1) > img.shape[1] * 0.03
        col_has_content = np.sum(gray < 250, axis=0) > img.shape[0] * 0.03
        
        rows = np.where(row_has_content)[0]
        cols = np.where(col_has_content)[0]
        
        if len(rows) == 0 or len(cols) == 0:
            return None
        
        y1, y2 = rows[0], rows[-1] + 1
        x1, x2 = cols[0], cols[-1] + 1
        
        # Add generous padding
        y1 = max(0, y1 - padding)
        y2 = min(img.shape[0], y2 + padding)
        x1 = max(0, x1 - padding)
        x2 = min(img.shape[1], x2 + padding)
        
        return img[y1:y2, x1:x2]
    
    def sanitize_filename(self, text: str) -> str:
        """Create safe filename from text"""
        # Remove special characters but keep meaningful ones
        text = re.sub(r'[<>:"/\\|?*]', '', text)
        # Replace spaces and other chars
        text = re.sub(r'[\s\-_]+', '_', text)
        # Remove leading/trailing underscores
        text = text.strip('_')
        # Limit length
        return text[:120]
    
    def process(self) -> Dict[str, Any]:
        """Main processing"""
        print(f"Processing PDF: {self.pdf_path}")
        print(f"Output directory: {self.output_dir}")
        print("\nExtracting images with folder structure...\n")
        
        product_data = {
            "product_name": self.product_name,
            "configurations": []
        }
        
        total_images = 0
        
        for page_num in range(len(self.doc)):
            print(f"Page {page_num + 1}/{len(self.doc)}...", end=" ")
            
            page_img = self.extract_page_as_image(page_num)
            text_blocks = self.extract_text_with_ocr(page_img)
            
            config_name = self.find_configuration_name(text_blocks, page_img.shape[0])
            if not config_name:
                config_name = f"Configuration_{page_num + 1}"
            
            print(f"[{config_name}]", end=" ")
            
            product_images = self.extract_images_between_text(page_img, text_blocks)
            
            if product_images:
                # Create folder for this configuration
                config_safe = self.sanitize_filename(config_name)
                config_folder = self.images_dir / config_safe
                config_folder.mkdir(exist_ok=True)
                
                config = {
                    "name": config_name,
                    "id": f"config_{page_num + 1}",
                    "page": page_num + 1,
                    "folder": config_safe,
                    "options": []
                }
                
                for idx, (cropped_img, desc_text, has_arrow) in enumerate(product_images):
                    # Use full description text
                    option_name = desc_text if desc_text else f"Option_{idx + 1}"
                    
                    # Create descriptive filename
                    option_safe = self.sanitize_filename(option_name)
                    
                    if not option_safe:
                        option_safe = f"Option_{idx+1}"
                    
                    # Add zoom indicator if arrows detected
                    if has_arrow:
                        option_safe += "_ZOOM"
                    
                    image_filename = f"{option_safe}.png"
                    image_path = config_folder / image_filename
                    
                    # Handle duplicates
                    counter = 1
                    while image_path.exists():
                        if has_arrow:
                            image_filename = f"{option_safe}_{counter}.png"
                        else:
                            image_filename = f"{option_safe}_{counter}.png"
                        image_path = config_folder / image_filename
                        counter += 1
                    
                    cv2.imwrite(str(image_path), cropped_img)
                    
                    config["options"].append({
                        "id": f"config_{page_num + 1}_option_{idx + 1}",
                        "name": option_name,
                        "image": f"{config_safe}/{image_filename}",
                        "has_zoom": has_arrow
                    })
                    
                    total_images += 1
                
                print(f"✓ {len(product_images)} image(s)")
                
                if config["options"]:
                    product_data["configurations"].append(config)
            else:
                print("(no images)")
        
        # Save JSON
        json_path = self.output_dir / f"{self.product_name}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(product_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*60}")
        print(f"✓ Complete!")
        print(f"✓ Configurations: {len(product_data['configurations'])}")
        print(f"✓ Product images extracted: {total_images}")
        print(f"✓ JSON: {json_path}")
        print(f"✓ Images: {self.images_dir}/")
        print(f"  Each configuration has its own folder")
        
        return product_data
    
    def close(self):
        if self.doc:
            self.doc.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_final.py <pdf_file> [output_directory]")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not Path(pdf_file).exists():
        print(f"Error: File not found: {pdf_file}")
        sys.exit(1)
    
    extractor = FinalProductExtractor(pdf_file, output_dir)
    try:
        extractor.process()
    finally:
        extractor.close()


if __name__ == "__main__":
    main()
