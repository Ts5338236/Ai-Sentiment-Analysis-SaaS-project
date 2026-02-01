from PIL import Image, ImageDraw
import os

# Create static directory if it doesn't exist
if not os.path.exists('static'):
    os.makedirs('static')
    print("Created static directory")

# Create a simple 16x16 image
img = Image.new('RGB', (16, 16), color='#496D89')  # Blue background
draw = ImageDraw.Draw(img)

# Draw a simple yellow square in the center
draw.rectangle([4, 4, 12, 12], fill='#FFFF00')  # Yellow square

# Save as favicon.ico
img.save('static/favicon.ico')
print("Favicon created successfully at static/favicon.ico")
