#!/usr/bin/env bash
# Extract images from PDF brochures and store in database
# Usage: ./scripts/extract-brochure-images.sh

set -e

cd /home/ubuntu/thai-car-intelligence

BROCHURE_DIR="storage/brochures"
OUTPUT_DIR="public/images/brochures"
mkdir -p "$OUTPUT_DIR"

echo "=== Brochure Image Extraction ==="

extract_brochure() {
  local pdf="$1"
  local model_slug="$2"
  local name="$3"
  
  echo "Processing: $name"
  
  if [ ! -f "$pdf" ]; then
    echo "  PDF not found: $pdf"
    return 0
  fi
  
  local img_dir="$OUTPUT_DIR/${model_slug}"
  mkdir -p "$img_dir"
  
  # Extract first 5 pages as images
  local count=0
  for page in 1 2 3 4 5; do
    local out_file="$img_dir/page-${page}.png"
    timeout 5 pdftoppm -png -r 72 -f "$page" -l "$page" "$pdf" "${img_dir}/page-${page}" 2>/dev/null || true
    if [ -f "$out_file" ]; then
      count=$((count + 1))
    fi
  done
  
  echo "  Extracted $count pages"
}

# Extract from existing brochures
extract_brochure "$BROCHURE_DIR/mg-urban-brochure-2026.pdf" "urban" "MG URBAN"
extract_brochure "$BROCHURE_DIR/honda-city-india-2026.pdf" "city" "Honda City"
extract_brochure "$BROCHURE_DIR/yaris-cross-catalogue-2026.pdf" "yaris-cross" "Toyota Yaris Cross"

# Update database with image paths
docker exec pgvector psql -U hermes -d thai_car_intelligence -c "
UPDATE \"Media\" SET url = '/images/brochures/urban/page-1.png' WHERE url LIKE '%mg-upload%' AND role = 'hero';
UPDATE \"Media\" SET url = '/images/brochures/city/page-1.png' WHERE url LIKE '%honda%' AND role = 'hero';
UPDATE \"Media\" SET url = '/images/brochures/yaris-cross/page-1.png' WHERE url LIKE '%toyota%' AND role = 'hero';
" 2>/dev/null || echo "  DB update skipped (manual update may be needed)"

echo ""
echo "=== Extraction Complete ==="
echo "Images stored in $OUTPUT_DIR"
