#!/bin/bash
set -e

echo "Installing Tesseract OCR..."

# Update package lists
apt-get update

# Install Tesseract
apt-get install -y tesseract-ocr libtesseract-dev

# Verify installation
which tesseract
tesseract --version

echo "Tesseract installed successfully!"
