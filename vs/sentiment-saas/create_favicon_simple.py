from PIL import Image, ImageDraw

# Create a simple 16x16 favicon
img = Image.new('RGB', (16, 16), color=(73, 109, 137))
d = ImageDraw.Draw(img)

# Draw a simple yellow square
d.rectangle([4, 4, 12, 12], fill=(255, 255, 0))

# Save as favicon.ico
img.save('static/favicon.ico')
print("Simple favicon created successfully at static/favicon.ico")
