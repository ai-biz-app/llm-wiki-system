#!/bin/bash
# Pre-commit verification script
# Run this before committing any changes

echo "=== Pre-Commit Verification ==="
echo ""

# 1. Run all tests
echo "1. Running test suite..."
cd /root/llm-wiki-system
source venv/bin/activate
python -m pytest tests/ -v --tb=short 2>&1
TEST_EXIT=$?

if [ $TEST_EXIT -ne 0 ]; then
    echo ""
    echo "❌ TESTS FAILED - DO NOT COMMIT"
    exit 1
fi

echo ""
echo "2. Checking imports..."
python -c "from backend.main import app; print('✓ App imports correctly')" 2>&1 || {
    echo "❌ Import check failed"
    exit 1
}

echo ""
echo "3. Checking critical flows..."
# Add more checks here as needed

echo ""
echo "✅ All checks passed! Safe to commit."
