#!/bin/bash
# Переменные
APP_NAME="Pricelist.app"
DMG_NAME="Pricelist"
VOLUME_NAME="Pricelist"

rm -rf dist/"$APP_NAME"
rm -rf dist/"$DMG_NAME.dmg"
rm -rf dist/"$VOLUME_NAME"

source .venv/bin/activate
pyinstaller main_mac.spec


#BACKGROUND_IMAGE="background.png"  # опционально

# Создаем временную директорию
mkdir -p temp_dir

# Копируем приложение
cp -R dist/"$APP_NAME" temp_dir/

# Создаем ссылку на папку "Программы"
ln -s /Applications temp_dir/

# Создаем DMG
hdiutil create -volname "$VOLUME_NAME" -srcfolder temp_dir -ov -format UDZO dist/"$DMG_NAME.dmg"

# Очищаем временные файлы
rm -rf temp_dir
rm -rf dist/"$VOLUME_NAME"

echo "DMG создан: ${DMG_NAME}.dmg"