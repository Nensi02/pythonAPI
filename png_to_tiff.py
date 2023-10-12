from PIL import Image
import os

imagename = input('image name without extension please:')
image = Image.open("images/png/" + imagename + '.png')
filename, extension = os.path.splitext(imagename)
if not extension:
    file = "images/tiff/" + imagename
    if not os.path.isdir('images/tiff'):
        os.mkdir('images/tiff')
    image.save(file, format = 'TIFF')
    print('file is saved!!')