#!/bin/bash
set -e

echo "🔧 Auto-fixing linting issues..."
echo ""

echo "📝 Step 1: Format code with ruff..."
python -m ruff format src/ tests/

echo ""
echo "🔍 Step 2: Fix linting errors (safe fixes)..."
python -m ruff check --fix src/ tests/

echo ""
echo "⚠️  Step 3: Fix linting errors (unsafe fixes - requires confirmation)..."
python -m ruff check --fix --unsafe-fixes src/ tests/ || true

echo ""
echo "✅ Linting fixes complete!"
echo ""
echo "📊 Running final check..."
python -m ruff format --check src/ tests/ && echo "✓ Formatting OK" || echo "✗ Some formatting issues remain"
python -m ruff check src/ tests/ && echo "✓ Linting OK" || echo "✗ Some linting issues remain"

echo ""
echo "🎯 Next steps:"
echo "1. Review the changes: git diff"
echo "2. Run tests: pytest tests/ -v"
echo "3. Commit: git add -A && git commit -m 'fix: Auto-fix linting issues'"
echo "4. Push: git push"
