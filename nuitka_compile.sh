nuitka \
  --standalone \
  --onefile \
  --macos-create-app-bundle \
  --macos-app-name="Pricelist" \
  --macos-app-mode=gui \
  --macos-app-icon="assets/icon.icns" \
  --output-dir=dist \
  --remove-output \
  --plugin-enable=anti-bloat \
  --plugin-no-detection \
  --include-data-files="db.sqlite3=db.sqlite3" \
  main.py